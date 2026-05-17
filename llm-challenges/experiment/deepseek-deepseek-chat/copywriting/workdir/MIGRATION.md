# Zrb CLI v1 → v2 Migration Guide

Zrb v2 introduces projects, paginated list responses, stricter authentication, and more consistent naming across the API. This guide covers every breaking change and provides the steps to migrate your existing integration.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [API Path Prefix](#2-api-path-prefix)
3. [Task ID: Integer → UUID](#3-task-id-integer--uuid)
4. [Field Rename: `done` → `completed`](#4-field-rename-done--completed)
5. [Task Creation Requires `project_id`](#5-task-creation-requires-project_id)
6. [List Responses Are Now Paginated](#6-list-responses-are-now-paginated)
7. [Migration Checklist](#7-migration-checklist)
8. [Upgrade](#8-upgrade)

---

## 1. Authentication

The request header for authentication has changed.

| v1 | v2 |
|---|---|
| `X-Auth-Token: <your_api_key>` | `Authorization: Bearer <your_api_token>` |

v2 rejects requests using `X-Auth-Token` with HTTP 401.

**Before (v1):**

```bash
curl https://api.zrb.io/tasks \
  -H "X-Auth-Token: abc123"
```

**After (v2):**

```bash
curl https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer abc123"
```

**Action:** Generate a v2 API token and update all request header code.

---

## 2. API Path Prefix

All endpoints are now prefixed with `/v2/`.

| Endpoint | v1 | v2 |
|---|---|---|
| List Tasks | `GET /tasks` | `GET /v2/tasks` |
| Get Task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create Task | `POST /tasks` | `POST /v2/tasks` |
| Update Task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete Task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**Before (v1):**

```python
response = client.get("/tasks")
```

**After (v2):**

```python
response = client.get("/v2/tasks")
```

**Action:** Update all base URLs and endpoint paths to include the `/v2/` prefix.

---

## 3. Task ID: Integer → UUID

Task identifiers are now UUID strings instead of auto-incrementing integers.

**Before (v1):**

```json
{"id": 42, "title": "Write tests", "done": false}
```

**After (v2):**

```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false}
```

This affects all endpoints that reference a task by ID:

- `GET /v2/tasks/{id}` — supply a UUID where you previously used an integer
- `PUT /v2/tasks/{id}`
- `DELETE /v2/tasks/{id}`
- Stored task references in your database, cache, or UI must be updated to UUIDs

**Before (v1):**

```javascript
// Fetching a task by integer ID
const task = await api.get(`/tasks/${42}`);
```

**After (v2):**

```javascript
// Fetching a task by UUID
const task = await api.get(`/v2/tasks/${taskUuid}`);
```

**Action:** Update all ID lookups, stored references, and the data type in your models.

---

## 4. Field Rename: `done` → `completed`

The task field `done` has been renamed to `completed`. The semantics are identical.

**Before (v1):**

```json
{"id": 1, "title": "Ship v1", "done": true}
```

**After (v2):**

```json
{"id": "a1b2c3d4-...", "title": "Ship v1", "completed": true}
```

**Before (v1) — Create/Update request:**

```json
{"title": "Update docs", "done": true}
```

**After (v2) — Create/Update request:**

```json
{"title": "Update docs", "completed": true}
```

**Action:**
- Update all code that reads `task.done` or `task["done"]` to use `task.completed` / `task["completed"]`
- Update all request bodies that send `done` to send `completed`
- Update any UI labels or logic that reference the field name

---

## 5. Task Creation Requires `project_id`

`POST /v2/tasks` now requires a `project_id` field in the request body. Omitting it returns HTTP 422.

**Before (v1):**

```bash
curl -X POST https://api.zrb.io/tasks \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

**Before (v1):**

```python
task = client.create_task({"title": "Refactor auth module"})
```

**After (v2):**

```python
task = client.create_task({
    "title": "Refactor auth module",
    "project_id": "proj_abc123"
})
```

**Action:**
- Obtain a valid `project_id` (use `GET /v2/projects` to list available projects)
- Add `project_id` to every task creation call
- Update any validation or UI that previously accepted a task without a project

---

## 6. List Responses Are Now Paginated

List endpoints (e.g., `GET /v2/tasks`) return a paginated envelope instead of a bare array.

**Before (v1):**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "e5f67890-...", "title": "Ship v1", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Use the `cursor` and `limit` query parameters for pagination:

```
GET /v2/tasks?cursor=cursor_xyz&limit=50
```

**Before (v1):**

```javascript
const tasks = await api.get("/tasks");
tasks.forEach(task => console.log(task.title));
```

**After (v2):**

```javascript
const { items, total, next_cursor } = await api.get("/v2/tasks");
items.forEach(task => console.log(task.title));

// Paginate
if (next_cursor) {
  const nextPage = await api.get(`/v2/tasks?cursor=${next_cursor}`);
}
```

**Action:**
- Unwrap list responses: read from the `items` key instead of the top-level array
- Update any type definitions: list endpoints now return an object, not an array
- Add pagination logic if you need more than one page of results

---

## 7. Migration Checklist

Use this checklist to track your migration progress.

### Authentication & URLs

- [ ] Generate v2 API tokens (Bearer tokens)
- [ ] Replace all `X-Auth-Token` headers with `Authorization: Bearer`
- [ ] Update all API endpoint paths to include the `/v2/` prefix

### Task Object Changes

- [ ] Update task ID handling: accept and store UUID strings instead of integers
- [ ] Migrate any stored task ID references (database, cache, config files) to UUIDs
- [ ] Rename all references to `done` → `completed` in request bodies and response parsing
- [ ] Update UI labels, form fields, and display logic from `done` to `completed`

### Task Creation

- [ ] Identify every code path that creates a task
- [ ] Add a `project_id` field to all create-task requests
- [ ] Update any creation forms or inputs to collect/assign a project

### List Responses

- [ ] Update response parsing: unwrap list responses from `items` key
- [ ] Update TypeScript/OpenAPI/type definitions for list endpoints
- [ ] Add pagination support if the default page size (20) is insufficient

### Validation

- [ ] Run your test suite against the v2 API
- [ ] Verify HTTP 401 (bad auth), 422 (missing project_id), 404 (unknown UUID) are handled correctly
- [ ] Test all CRUD operations end-to-end

---

## 8. Upgrade

To install the v2 CLI:

```bash
pip install --upgrade zrb
```

Verify the installation:

```bash
zrb --version
# Expected: 2.x.x
```
