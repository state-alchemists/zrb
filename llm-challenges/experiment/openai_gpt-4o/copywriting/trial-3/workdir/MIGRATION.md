# Zrb Task API — v1 to v2 Migration Guide

Zrb API v2 introduces projects, paginated lists, UUID-based task IDs, and stricter authentication. This guide covers every breaking change with before/after examples so you can upgrade your integration with confidence.

---

## At a Glance: All Breaking Changes

| # | Change | v1 | v2 |
|---|--------|----|----|
| 1 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 2 | Auth header | `X-Auth-Token` | `Authorization: Bearer` |
| 3 | Task ID type | Integer | UUID string |
| 4 | Completion field | `done` | `completed` |
| 5 | Project requirement | Not required | `project_id` required on create |
| 6 | List response format | Bare array | Paginated envelope |

---

## 1. Endpoint Prefix: `/tasks` → `/v2/tasks`

All v2 endpoints are prefixed with `/v2/`. The v1 paths no longer resolve.

**Before (v1):**

```http
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**

```http
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication: `X-Auth-Token` → `Authorization: Bearer`

The custom `X-Auth-Token` header is replaced by the standard Bearer token scheme. Requests using the old header receive HTTP 401.

**Before (v1):**

```http
X-Auth-Token: your_api_key
```

**After (v2):**

```http
Authorization: Bearer your_api_token
```

**Client library update example (Python):**

```python
# v1
headers = {"X-Auth-Token": "your_api_key"}

# v2
headers = {"Authorization": "Bearer your_api_token"}
```

---

## 3. Task ID: Integer → UUID String

Task IDs are now UUID strings instead of auto-incrementing integers. All endpoints that reference a task by ID must use the string form.

**Before (v1):**

```json
{"id": 42, "title": "Write tests", "done": false}
```

**After (v2):**

```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false}
```

**Impact on client code:**

- URL construction: `GET /tasks/42` → `GET /v2/tasks/a1b2c3d4-...`
- Local comparisons: switch from integer equality to string equality
- Storage: widen any database columns or cache keys to hold 36-character UUIDs
- Cached task references: re-fetch or re-key existing data

---

## 4. Field Rename: `done` → `completed`

The boolean field that tracks task completion has been renamed from `done` to `completed`. The old field is not present in v2 responses and is ignored in v2 requests.

**Reading a task (before → after):**

```javascript
// v1
if (task.done) { console.log("Complete"); }

// v2
if (task.completed) { console.log("Complete"); }
```

**Updating a task (before → after):**

```json
// v1 — PUT /tasks/42
{"done": true}

// v2 — PUT /v2/tasks/{uuid}
{"completed": true}
```

---

## 5. New Required Field: `project_id`

All tasks must belong to a project. The `project_id` field is now required when creating a task. Omitting it returns HTTP 422.

**Before (v1) — Create:**

```json
POST /tasks
{"title": "New task"}
```

**After (v2) — Create:**

```json
POST /v2/tasks
{"title": "New task", "project_id": "proj_abc123"}
```

**Migration strategy:** If you don't yet have a project model, create a default project (e.g., `proj_default`) and use its ID for all existing tasks during the transition.

---

## 6. List Response: Bare Array → Paginated Envelope

List endpoints no longer return a bare array. All list responses now use a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1) — List response:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) — List response:**

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "e5f6a7b8-...", "title": "Ship v1", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Pagination pattern (JavaScript):**

```javascript
// v1
const tasks = await fetch("/tasks").then(r => r.json());

// v2 — first page
const page = await fetch("/v2/tasks?limit=20").then(r => r.json());
const tasks = page.items;

// v2 — next page
const nextPage = await fetch("/v2/tasks?cursor=" + page.next_cursor).then(r => r.json());
```

Pass `?cursor=<next_cursor>` and optionally `?limit=<N>` (default 20) to paginate. When `next_cursor` is absent or null, there are no more pages.

---

## Quick Reference: Operation Comparison

| Operation | v1 | v2 |
|-----------|----|----|
| Auth header | `X-Auth-Token: <key>` | `Authorization: Bearer <token>` |
| List tasks | `GET /tasks` → `[...]` | `GET /v2/tasks?limit=20` → `{items, total, next_cursor}` |
| Get task | `GET /tasks/42` | `GET /v2/tasks/{uuid}` |
| Create task | `POST /tasks` `{title}` | `POST /v2/tasks` `{title, project_id}` |
| Update task | `PUT /tasks/42` `{done: true}` | `PUT /v2/tasks/{uuid}` `{completed: true}` |
| Delete task | `DELETE /tasks/42` | `DELETE /v2/tasks/{uuid}` |

---

## Migration Checklist

Use this step-by-step checklist to upgrade your integration:

- [ ] **Update endpoint URLs** — prefix all paths with `/v2/`
- [ ] **Update authentication** — replace `X-Auth-Token` header with `Authorization: Bearer`
- [ ] **Obtain a new API token** — v1 API keys do not work with v2; generate a Bearer token via the dashboard
- [ ] **Update task ID handling** — change all ID fields, variables, and URL parameters from integer to UUID string
- [ ] **Update `done` → `completed`** — rename the field in all read paths, write paths, and data models
- [ ] **Add `project_id`** — include a valid `project_id` in every create-task request; create a default project if needed
- [ ] **Update list response parsing** — unwrap the paginated envelope (access `.items` instead of using the response directly)
- [ ] **Implement pagination** — check `next_cursor` and loop with `?cursor=` to fetch all pages where needed
- [ ] **Migrate local data** — update stored task IDs, caches, and database schemas to use UUID strings; re-fetch where possible
- [ ] **Update API client libraries** — regenerate or patch any SDKs, OpenAPI clients, or curl wrappers

---

## Upgrade Command

Ready to switch? Install the latest Zrb CLI and all dependencies:

```bash
pipx install zrb@latest
```

Or, if you're using pip / Poetry:

```bash
pip install --upgrade "zrb>=2.0.0"
```

Once installed, verify the version:

```bash
zrb --version
```
