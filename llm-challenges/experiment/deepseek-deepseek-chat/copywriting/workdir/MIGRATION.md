# Migrating from Zrb API v1 to v2

v2 introduces projects, cursor-based pagination, and stricter authentication. This guide covers every breaking change with before/after examples so you can upgrade your integration with confidence.

---

## Table of Contents

- [1. Base URL: `/v2/` prefix added](#1-base-url-v2-prefix-added)
- [2. Authentication: Bearer token replaces `X-Auth-Token`](#2-authentication-bearer-token-replaces-x-auth-token)
- [3. Task `id`: integer → UUID string](#3-task-id-integer--uuid-string)
- [4. Task `done` → `completed`](#4-task-done--completed)
- [5. Task creation now requires `project_id`](#5-task-creation-now-requires-project_id)
- [6. List endpoints return a paginated envelope](#6-list-endpoints-return-a-paginated-envelope)
- [Migration Checklist](#migration-checklist)
- [Upgrade Command](#upgrade-command)

---

## 1. Base URL: `/v2/` prefix added

All endpoints are now prefixed with `/v2/`. Requests to the old paths will fail.

**Before (v1):**

```
GET /tasks
POST /tasks
GET /tasks/{id}
```

**After (v2):**

```
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/{id}
```

**Action:** Update all URL paths in your client configuration or SDK.

---

## 2. Authentication: Bearer token replaces `X-Auth-Token`

The `X-Auth-Token` header is no longer accepted. Requests using it will receive HTTP 401. Use the `Authorization: Bearer` header instead.

**Before (v1):**

```
X-Auth-Token: <your_api_key>
```

**After (v2):**

```
Authorization: Bearer <your_api_token>
```

**Action:** Replace your auth header logic and rotate to a v2-compatible token if needed.

---

## 3. Task `id`: integer → UUID string

Task IDs are now UUID v4 strings. Any code that assumes an integer `id` (e.g., numeric comparisons, sequential iteration, integer-based storage) must be updated.

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
  "completed": false
}
```

**Impact:**
- References to `/tasks/{id}` now expect a UUID in the path.
- Local caches or databases keyed on integer `id` need schema migration.
- Sorting by `id` will now sort lexicographically, not numerically.

---

## 4. Task `done` → `completed`

The field `done` has been renamed to `completed`. Both reading and writing operations must use the new name.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": true
}
```

```bash
# v1 — update task
curl -X PUT /tasks/42 -d '{"done": true}'
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-...",
  "title": "Write tests",
  "completed": true
}
```

```bash
# v2 — update task
curl -X PUT /v2/tasks/a1b2c3d4-... -d '{"completed": true}'
```

**Action:** Search your codebase for `done` references in request bodies, response parsing, and data models. Replace with `completed`.

---

## 5. Task creation now requires `project_id`

In v1, creating a task only required a `title`. v2 introduces projects — every task must belong to one. Omitting `project_id` returns HTTP 422.

**Before (v1):**

```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Action:** Obtain a valid `project_id` (see the List Projects endpoint). Add it to every create-task call. Update any UI or CLI flow that previously let users create tasks without selecting a project.

---

## 6. List endpoints return a paginated envelope

In v1, `GET /tasks` returned a bare JSON array. In v2, it returns a paginated envelope object with cursor-based pagination. Raw array parsing will break.

**Before (v1):**

```json
GET /tasks
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

```javascript
// v1 — direct array access
const tasks = response.data;        // ✅ works
const first = response.data[0];     // ✅ works
```

**After (v2):**

```json
GET /v2/tasks
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false},
    {"id": "c3d4...", "title": "Ship v1", "completed": true}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// v2 — access via envelope
const tasks = response.data.items;         // ✅
const first = response.data.items[0];      // ✅
```

**Pagination:**

Pass `?cursor=<next_cursor>` to fetch the next page. Optionally set `?limit=N` (default 20) to control page size.

```bash
curl /v2/tasks?cursor=cursor_xyz&limit=50
```

**Action:** Update all list-response parsing to read from `.items`. Add pagination handling using `next_cursor`.

---

## Migration Checklist

1. **Base URLs** — Add `/v2/` prefix to every endpoint path.
2. **Auth header** — Replace `X-Auth-Token` with `Authorization: Bearer`.
3. **Token rotation** — Issue v2-compatible tokens if your auth provider requires it.
4. **ID handling** — Update `id` field type from integer to UUID string in all data models, DB schemas, and caches.
5. **`done` → `completed`** — Rename the field everywhere: request bodies, response parsers, data models, and UI components.
6. **Project membership** — Add `project_id` to every task creation call.
7. **List envelope** — Update response parsing to extract `.items` from the paginated envelope.
8. **Pagination** — Implement cursor-based pagination for all list endpoints.
9. **Test** — Run your integration suite against a v2 staging environment.
10. **Deploy** — Cut over to v2 endpoints after verification.

---

## Upgrade Command

Install or update to the latest v2 release:

```bash
pip install --upgrade zrb
```

Verify the installed version:

```bash
zrb --version
# v2.0.0 or later
```
