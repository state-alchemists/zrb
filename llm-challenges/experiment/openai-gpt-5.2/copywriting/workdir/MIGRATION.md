# Zrb Task API v1 → v2 Migration Guide

This guide helps existing Zrb v1 integrators migrate to the v2 Task API.

## At a glance (all breaking changes)

v2 introduces the following **breaking** changes:

1. **All endpoints are now prefixed with `/v2/`**
2. **Authentication changed from `X-Auth-Token` to `Authorization: Bearer …`**
3. **Task `id` changed type: integer → UUID string**
4. **Task field renamed: `done` → `completed`**
5. **Create task now requires `project_id`**
6. **List endpoints return a paginated envelope (not a bare array)**

---

## 1) Base path change: `/tasks` → `/v2/tasks`

**What broke**
- Every endpoint is now under the `/v2/` prefix.
- Any client still calling `/tasks…` will hit the wrong route (likely 404).

**Before (v1)**
```http
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2)**
```http
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2) Authentication change: `X-Auth-Token` → `Authorization: Bearer …`

**What broke**
- v1 used an API key in `X-Auth-Token`.
- v2 requires a Bearer token in the standard `Authorization` header.
- Requests with `X-Auth-Token` will receive **HTTP 401**.

**Before (v1)**
```http
GET /tasks
X-Auth-Token: <your_api_key>
```

**After (v2)**
```http
GET /v2/tasks
Authorization: Bearer <your_api_token>
```

---

## 3) Task identifier type change: integer `id` → UUID string `id`

**What broke**
- In v1, task IDs are integers (e.g. `42`).
- In v2, task IDs are UUID strings (e.g. `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

Impacts:
- URL construction (`/tasks/{id}`) must treat `id` as a string.
- Database schemas, typed clients, and validations must accept UUID format.

**Before (v1 task object)**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2 task object)**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## 4) Field rename: `done` → `completed`

**What broke**
- v1 used `done`.
- v2 uses `completed`.

Impacts:
- JSON decoding/encoding will fail or silently drop the field if not updated.
- Update payloads must send `completed`, not `done`.

**Before (v1 update)**
```http
PUT /tasks/42
Content-Type: application/json

{
  "done": true
}
```

**After (v2 update)**
```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json

{
  "completed": true
}
```

---

## 5) Create requires `project_id`

**What broke**
- v1 could create a task with only `title`.
- v2 requires **both** `title` and `project_id`.
- Omitting `project_id` returns **HTTP 422**.

**Before (v1 create)**
```http
POST /tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

**After (v2 create)**
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

## 6) List response shape changed: bare array → paginated envelope

**What broke**
- v1 `GET /tasks` returned a **bare JSON array**.
- v2 `GET /v2/tasks` returns an object envelope with:
  - `items`: the array of tasks
  - `total`: total available tasks
  - `next_cursor`: cursor for the next page (or null/absent when done)

Impacts:
- Any code that assumes the response is an array (e.g. `for task in response`) must be updated to read `response.items`.
- Pagination is cursor-based; you must pass `?cursor=...` to continue.
- You can control page size via `limit` (default 20).

**Before (v1 list)**
```http
GET /tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2 list)**
```http
GET /v2/tasks?limit=20
```

```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Buy milk",
      "completed": false,
      "project_id": "proj_abc123",
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Fetching the next page (v2)**
```http
GET /v2/tasks?cursor=cursor_xyz&limit=20
```

---

## Step-by-step migration checklist

1. **Update your base URL builder** to add the `/v2/` prefix to all task routes.
2. **Switch auth headers**:
   - Stop sending `X-Auth-Token`.
   - Send `Authorization: Bearer <token>`.
3. **Update ID handling**:
   - Treat `task.id` as a string.
   - Update validations/types (UUID) and any persistence that assumed integers.
4. **Rename fields in your models/DTOs**:
   - Map `done` → `completed` in both parsing and serialization.
5. **Update task creation flows**:
   - Ensure `project_id` is provided for every create.
   - Decide how you source/select a `project_id` in your app.
6. **Fix list parsing and pagination**:
   - Read `items` instead of assuming the top-level response is an array.
   - Implement cursor pagination using `next_cursor` and `?cursor=...`.
   - Optionally tune `limit` (default 20).
7. **Run your integration tests** against v2 endpoints (especially create/list/update).
8. **Deploy** your updated client.

---

## Upgrade command

```sh
zrb upgrade --major v2
```
