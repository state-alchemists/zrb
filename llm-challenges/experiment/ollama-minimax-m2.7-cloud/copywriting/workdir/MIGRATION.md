# Zrb CLI v1 → v2 Migration Guide

This guide covers every breaking change from v1 to v2 and how to update your integration.

## Breaking Changes Overview

| # | Change | Severity |
|---|--------|----------|
| 1 | All endpoints prefixed with `/v2/` | High |
| 2 | Authentication: `X-Auth-Token` → Bearer token | High |
| 3 | Task `id` changed from integer to UUID string | Medium |
| 4 | Task field `done` renamed to `completed` | Medium |
| 5 | Task creation requires `project_id` | High |
| 6 | List response: bare array → paginated envelope | Medium |

---

## 1. Endpoint Prefix

All endpoints now include the `/v2/` prefix.

### Before (v1)
```http
GET /tasks
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

### After (v2)
```http
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication Header

The authentication header has changed from a custom header to a standard Bearer token.

### Before (v1)
```http
X-Auth-Token: your_api_key_here
```

### After (v2)
```http
Authorization: Bearer your_api_token_here
```

Requests with `X-Auth-Token` will receive **HTTP 401**.

---

## 3. Task ID Type

Task IDs are now UUIDs instead of integers.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

**Action required:** Update your code to handle UUID strings instead of integers for task IDs.

---

## 4. Task Field Renamed: `done` → `completed`

The boolean status field has been renamed.

### Before (v1)
```json
{
  "id": 1,
  "title": "Ship v1",
  "done": true
}
```

### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v2",
  "completed": true
}
```

**Action required:** Replace all references to `task.done` with `task.completed` in your code.

---

## 5. Task Creation Requires `project_id`

Creating a task now requires associating it with a project.

### Before (v1)
```http
POST /tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

### After (v2)
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

Omitting `project_id` returns **HTTP 422**.

---

## 6. List Response Format

List endpoints no longer return a bare array. They return a paginated envelope.

### Before (v1)
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2)
```json
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

### Pagination

Use the `cursor` query parameter to paginate:

```http
GET /v2/tasks?cursor=cursor_xyz&limit=20
```

- `limit` defaults to 20 if not specified
- `next_cursor` is `null` when there are no more pages

---

## Migration Checklist

- [ ] Update all endpoint URLs from `/tasks` to `/v2/tasks`
- [ ] Change authentication header from `X-Auth-Token` to `Authorization: Bearer <token>`
- [ ] Replace integer task IDs with UUID string handling
- [ ] Rename all `done` field references to `completed`
- [ ] Add `project_id` to all task creation requests
- [ ] Update list response parsing to extract `items` array from envelope
- [ ] Implement pagination logic using `next_cursor`
- [ ] Update existing stored task IDs to UUID format

---

## Upgrade Command

```bash
rbenv install 2.0.0 && rbenv global 2.0.0
```
