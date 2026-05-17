# Zrb CLI v1 → v2 Migration Guide

This guide covers every breaking change in Zrb CLI v2 and how to migrate your existing code.

## Overview

v2 introduces projects, cursor-based pagination, and stricter authentication. Six breaking changes require updates to any v1 integration.

| Change | Impact |
|--------|--------|
| Endpoint prefix `/v2/` | Update all URL paths |
| Bearer token auth | Update auth header format |
| ID type: integer → UUID | Update ID handling in your code |
| Field `done` → `completed` | Update task object references |
| `project_id` required on create | Add project context to task creation |
| List returns envelope | Update response parsing for list endpoints |

---

## Breaking Changes

### 1. Endpoint Prefix

All endpoints now live under `/v2/`. Requests to `/tasks` will return 404.

**Before (v1)**
```http
GET /tasks
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2)**
```http
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication Header

The `X-Auth-Token` header is no longer accepted. v2 uses the standard `Authorization` header with a Bearer token.

**Before (v1)**
```http
X-Auth-Token: your_api_key_here
```

**After (v2)**
```http
Authorization: Bearer your_api_token_here
```

If you send `X-Auth-Token`, the server returns HTTP 401.

---

### 3. Task ID Type

Task IDs are now UUID strings instead of integers.

**Before (v1)**
```json
{"id": 42, "title": "Write tests", "done": false}
```

**After (v2)**
```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false}
```

Update any code that treats task ID as an integer (sorting, comparisons, database columns, URL path segments).

---

### 4. Task Field Renamed

The `done` boolean is renamed to `completed`.

**Before (v1)**
```json
{"id": 1, "title": "Ship v1", "done": true}
```

**After (v2)**
```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Ship v2", "completed": true}
```

Update JSON serialization, database columns, and any conditional logic referencing `done`.

---

### 5. Project ID Required on Create

Task creation now requires a `project_id`. Omitting it returns HTTP 422.

**Before (v1)**
```json
POST /tasks
{"title": "New task"}
```

**After (v2)**
```json
POST /v2/tasks
{"title": "New task", "project_id": "proj_abc123"}
```

You must provision a project before creating tasks. See your project dashboard or use `zb project create` to create one.

---

### 6. List Response Format

List endpoints return a paginated envelope instead of a bare array.

**Before (v1)**
```json
GET /tasks
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**After (v2)**
```json
GET /v2/tasks
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123"},
    {"id": "...", "title": "Ship v2", "completed": true, "project_id": "proj_abc123"}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Access tasks via `response["items"]`. For pagination, pass `?cursor=<next_cursor>` in subsequent requests. The `limit` query param controls page size (default 20).

---

## Migration Checklist

Run through these steps in order:

- [ ] **Update endpoint URLs** — add `/v2` prefix to all task paths
- [ ] **Update auth header** — replace `X-Auth-Token` with `Authorization: Bearer <token>`
- [ ] **Update ID handling** — change integer ID fields/locals to string/uuid
- [ ] **Rename `done` to `completed`** — JSON keys, database columns, conditional checks
- [ ] **Add `project_id` to task create** — fetch or create a project first, include its ID on task creation
- [ ] **Update list parsing** — extract tasks from `response["items"]` instead of using the response directly
- [ ] **Add pagination logic** — handle `next_cursor` for large result sets
- [ ] **Update tests** — use UUID strings and the new response envelope
- [ ] **Verify with a live request** — create a task, retrieve it, list it, delete it

---

## Upgrade Command

```bash
zb upgrade
```

After upgrading, test your integration against the v2 endpoints. The v1 API will be decommissioned in a future release.