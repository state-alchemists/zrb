# Zrb Task API v1 → v2 Migration Guide

This guide covers all breaking changes when upgrading from Zrb CLI v1 to v2. If you're currently using v1, read this carefully before upgrading.

---

## Breaking Changes Overview

| # | Change | Impact |
|---|--------|--------|
| 1 | Endpoint prefix `/v2/` added | All API calls |
| 2 | Authentication header changed | All API calls |
| 3 | Task `id` type changed | Create/Update/Delete operations |
| 4 | Field `done` renamed to `completed` | Read/Write operations |
| 5 | `project_id` now required | Task creation |
| 6 | List responses paginated | List operations |

---

## 1. Endpoint Prefix

All endpoints are now prefixed with `/v2/`.

### Before (v1)

```bash
GET /tasks
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

### After (v2)

```bash
GET /v2/tasks
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

## 2. Authentication Header

The authentication header has changed from a custom header to a standard Bearer token.

### Before (v1)

```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.dev/tasks
```

### After (v2)

```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.dev/v2/tasks
```

**Note:** Requests using the old `X-Auth-Token` header will receive HTTP 401 Unauthorized.

---

## 3. Task ID Type Change

Task IDs have changed from integers to UUID strings.

### Before (v1)

```json
{
  "id": 42,
  "title": "Write tests"
}
```

### After (v2)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

**Impact:** Update any code that:
- Assumes integer IDs for type checking
- Stores IDs as `int` in databases or structs
- Uses arithmetic on IDs

---

## 4. Field Rename: `done` → `completed`

The `done` field has been renamed to `completed`.

### Before (v1)

```json
{
  "id": 42,
  "title": "Buy milk",
  "done": false
}
```

### After (v2)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Buy milk",
  "completed": false
}
```

**Impact:** Update any code that:
- Reads or writes the `done` field
- Uses the field name in queries or filters

---

## 5. Required `project_id` for Task Creation

Creating a task now requires a `project_id`.

### Before (v1)

```json
POST /tasks
{
  "title": "New task title"
}
```

### After (v2)

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Note:** Omitting `project_id` returns HTTP 422 Unprocessable Entity.

---

## 6. Paginated List Responses

List endpoints now return a paginated envelope instead of a bare array.

### Before (v1)

```bash
GET /tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2)

```bash
GET /v2/tasks
```

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "e5f6g7h8-...", "title": "Ship v2", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Pagination parameters:**
- `cursor` — pagination cursor (optional)
- `limit` — max results per page (default: 20)

### Paginating Through Results

To fetch the next page:

```bash
GET /v2/tasks?cursor=cursor_xyz
```

**Impact:** Update any code that:
- Expects a bare array at the root level
- Iterates directly over the response

---

## Migration Checklist

Complete these steps to migrate your application:

- [ ] Update base URL to include `/v2/` prefix
- [ ] Change auth header from `X-Auth-Token` to `Authorization: Bearer`
- [ ] Update `id` handling from integer to UUID string
- [ ] Rename all `done` field references to `completed`
- [ ] Add `project_id` parameter to all task creation calls
- [ ] Wrap list response handling to extract `items` array
- [ ] Implement pagination handling using `next_cursor`
- [ ] Update data models/structs to match new schema
- [ ] Update any database column types storing task IDs (int → varchar/uuid)
- [ ] Run integration tests against v2 API

---

## Upgrade Command

```bash
npm install zrb-cli@2
```