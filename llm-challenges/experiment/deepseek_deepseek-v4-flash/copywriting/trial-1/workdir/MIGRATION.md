# Zrb API v2 Migration Guide

> **Audience:** Developers currently using the v1 API.
> **Goal:** Migrate your client code from v1 to v2 with minimal downtime.
> **Estimated effort:** 30–60 minutes per integration.

v2 introduces projects, cursor-based pagination, and stricter authentication.
Every breaking change is detailed below with a before/after example. Run the
upgrade command at the bottom when you're ready.

---

## Table of Contents

1. [Breaking Changes at a Glance](#breaking-changes-at-a-glance)
2. [Authentication](#1-authentication-header)
3. [Endpoint Base Path](#2-endpoint-base-path)
4. [Task ID Type (Integer to UUID)](#3-task-id-type-integer-to-uuid-string)
5. [Field Rename: `done` → `completed`](#4-task-field-done--completed)
6. [Required `project_id` on Creation](#5-required-project_id-on-task-creation)
7. [List Response Envelope & Cursor Pagination](#6-list-response-envelope--cursor-pagination)
8. [Migration Checklist](#migration-checklist)
9. [Upgrade Command](#upgrade-command)

---

## Breaking Changes at a Glance

| Change | v1 | v2 |
|--------|----|----|
| Auth header | `X-Auth-Token` | `Authorization: Bearer <token>` |
| Base path | `/tasks` | `/v2/tasks` |
| Task `id` type | integer (e.g. `42`) | UUID string (e.g. `"a1b2c3d4-..."`) |
| Task status field | `done` | `completed` |
| Task creation | `title` only | `title` + required `project_id` |
| List response | bare array | envelope (`{items, total, next_cursor}`) |
| Pagination | none | cursor-based (`?cursor=...`) |

---

## 1. Authentication Header

The authentication header has changed from a static token header to the
standard Bearer scheme. v1 tokens are not forwarded — you need a new v2 API
token.

**Before (v1):**

```http
X-Auth-Token: <your_api_key>
```

**After (v2):**

```http
Authorization: Bearer <your_v2_api_token>
```

Requests that still send `X-Auth-Token` will receive **HTTP 401 Unauthorized**
with no body.

**Client-side change (curl):**

```bash
# v1
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks

# v2
curl -H "Authorization: Bearer abc123-v2" https://api.zrb.dev/v2/tasks
```

---

## 2. Endpoint Base Path

All endpoints are now prefixed with `/v2/`. The old bare paths return 404.

| Endpoint | v1 | v2 |
|----------|----|----|
| List Tasks | `GET /tasks` | `GET /v2/tasks` |
| Get Task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create Task | `POST /tasks` | `POST /v2/tasks` |
| Update Task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete Task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**Before (v1):**

```http
GET /tasks/42
```

**After (v2):**

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 3. Task ID Type (Integer to UUID String)

Task IDs are now UUID v4 strings instead of auto-incrementing integers.
Any code that stores, compares, or constructs task IDs with integer types
must be updated to handle strings.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123"
}
```

**Client-side change (JavaScript):**

```js
// v1 — integer ID
const id = 42;
const response = await fetch(`/tasks/${id}`);

// v2 — string UUID
const id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
const response = await fetch(`/v2/tasks/${id}`);
```

**Client-side change (Python):**

```python
# v1 — integer ID
task_id = 42
response = requests.get(f"{base}/tasks/{task_id}")

# v2 — string UUID
import uuid
task_id = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
response = requests.get(f"{base}/v2/tasks/{task_id}")
```

> **Note:** v2 does not expose a mapping from old integer IDs to new UUIDs.
> If you have cached references, you will need to re-resolve them by title
> or other unique attributes.

---

## 4. Task Field: `done` → `completed`

The `done` boolean field has been renamed to `completed`. The semantics are
identical — `true` / `false` — only the key changed.

**Read path:**

```python
# v1
task["done"]   # True / False

# v2
task["completed"]  # True / False
```

**Write path (Update Task):**

```http
# v1
PUT /tasks/42
Content-Type: application/json

{"done": true}

# v2
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json

{"completed": true}
```

Including the old `done` key in a v2 request body is silently ignored —
it will not set the task status.

---

## 5. Required `project_id` on Task Creation

Every task now belongs to a project. The `project_id` field is **required**
when creating a task. Omitting it returns **HTTP 422 Unprocessable Entity**.

You must obtain a valid `project_id` before creating tasks. Projects can be
created or listed via the (unchanged from alpha) `/v2/projects` endpoint.

**Before (v1):**

```http
POST /tasks
Content-Type: application/json

{"title": "Write tests"}
```

**After (v2):**

```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "Write tests",
  "project_id": "proj_abc123"
}
```

**Client-side validation check:**

```python
# v2 — project_id is mandatory
def create_task(title: str, project_id: str) -> dict:
    if not project_id:
        raise ValueError("project_id is required")
    response = requests.post(
        f"{base}/v2/tasks",
        headers={"Authorization": "Bearer ..."},
        json={"title": title, "project_id": project_id},
    )
    response.raise_for_status()
    return response.json()
```

If you don't have existing projects, create one first:

```bash
curl -X POST https://api.zrb.dev/v2/projects \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project"}'
```

The response includes a `project_id` to use for subsequent task creation.

---

## 6. List Response Envelope & Cursor Pagination

List endpoints no longer return a bare array. v2 wraps results in a
paginated envelope and uses cursor-based pagination instead of offset/limit.

**Before (v1) — bare array, no pagination:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) — envelope with cursor:**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false,
     "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3...", "title": "Ship v2", "completed": true,
     "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Client-side change (JavaScript):**

```js
// v1
const tasks = await response.json();
tasks.forEach(t => console.log(t.title));

// v2
const envelope = await response.json();
const { items: tasks, total, next_cursor } = envelope;
tasks.forEach(t => console.log(t.title));
```

**Fetching the next page:**

```bash
curl "https://api.zrb.dev/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer <token>"
```

Default page size is **20 items**. Pass `?limit=` to change it (max 100).

When `next_cursor` is `null`, there are no more pages.

---

## Migration Checklist

Use this checklist to track your migration progress. Each item links to the
corresponding section above.

- [ ] **Regenerate API tokens** — Issue new v2 tokens ([§1](#1-authentication-header)).
- [ ] **Update auth header** — Replace `X-Auth-Token` with `Authorization: Bearer` ([§1](#1-authentication-header)).
- [ ] **Update base URLs** — Prefix all endpoints with `/v2/` ([§2](#2-endpoint-base-path)).
- [ ] **Migrate task ID storage** — Change integer columns/variables to UUID strings ([§3](#3-task-id-type-integer-to-uuid-string)).
- [ ] **Rename field reads** — Change all `task["done"]` / `task.done` to `task["completed"]` / `task.completed` ([§4](#4-task-field-done--completed)).
- [ ] **Rename field writes** — Change `{"done": ...}` to `{"completed": ...}` in create and update payloads ([§4](#4-task-field-done--completed)).
- [ ] **Add project_id to creation** — Obtain or create a project, then include `project_id` in every `POST /v2/tasks` ([§5](#5-required-project_id-on-task-creation)).
- [ ] **Update list response parsing** — Access `.items` (or `items`) instead of reading the response as a bare array ([§6](#6-list-response-envelope--cursor-pagination)).
- [ ] **Add pagination handling** — Implement cursor-based loop for list endpoints that may return multiple pages ([§6](#6-list-response-envelope--cursor-pagination)).
- [ ] **Update local caches / databases** — Reindex any stored task records with UUID IDs, new field names, and associated `project_id` ([§3](#3-task-id-type-integer-to-uuid-string), [§4](#4-task-field-done--completed), [§5](#5-required-project_id-on-task-creation)).
- [ ] **Run integration tests** — Test each endpoint against a v2 staging environment before deploying to production.

---

## Upgrade Command

To upgrade your Zrb CLI to v2, run:

```bash
pip install --upgrade zrb
```

Verify the installed version:

```bash
zrb --version
# Should output: zrb v2.x.x
```

If you are using a specific v1 version and need to lock the upgrade:

```bash
pip install "zrb>=2.0.0,<3.0.0"
```

---

> Questions or issues? Open a ticket at [github.com/state-alchemists/zrb/issues](https://github.com/state-alchemists/zrb/issues).
