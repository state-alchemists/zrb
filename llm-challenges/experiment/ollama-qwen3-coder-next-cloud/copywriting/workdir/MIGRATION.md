# Zrb CLI v2 Migration Guide

This guide helps experienced developers migrate from Zrb CLI v1 to v2. v2 introduces breaking changes to improve security, consistency, and scalability. This document outlines each breaking change with before/after examples and a step-by-step checklist.

---

## Breaking Changes

### 1. Endpoint Path Prefix

All API endpoints are now prefixed with `/v2/`.

**Before (v1):**
```
GET /tasks
POST /tasks
PUT /tasks/42
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication Header

The authentication header changed from `X-Auth-Token` to Bearer token format.

**Before (v1):**
```bash
curl -H "X-Auth-Token: my_api_key" https://api.zrb.io/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer my_api_token" https://api.zrb.io/v2/tasks
```

*Note: Requests with `X-Auth-Token` will receive HTTP 401.*

---

### 3. Task ID Type Change

Task IDs changed from integer to UUID string format.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

*Impact: Any code that assumes task IDs are integers must be updated to handle UUID strings.*

---

### 4. `done` Field Renamed to `completed`

The task object's `done` field is now `completed` for clearer semantics.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": true
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true
}
```

*Impact: Update all request bodies and response parsing to use `completed` instead of `done`.*

---

### 5. Project ID Required on Creation

Task creation now requires a `project_id` field.

**Before (v1):**
```bash
curl -X POST https://api.zrb.io/tasks \
  -H "X-Auth-Token: my_api_key" \
  -d '{"title": "New task"}'
```

**After (v2):**
```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer my_api_token" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

*Response: HTTP 422 if `project_id` is omitted.*

---

### 6. Paginated List Responses

List endpoints now return a structured envelope instead of a bare array.

**Before (v1):**
```json
[
  {"id": 1, "title": "Task 1", "done": false},
  {"id": 2, "title": "Task 2", "done": true}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Task 1", "completed": false, "project_id": "proj_abc"},
    {"id": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "title": "Task 2", "completed": true, "project_id": "proj_def"}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

*Query params:*
- `?cursor=<cursor>` — fetch next page
- `?limit=50` — customize page size (default: 20)

*Impact: Update pagination logic to handle the envelope structure and cursor-based traversal.*

---

## Migration Checklist

Follow these steps to migrate your codebase:

1. **Update endpoint URLs**
   - Prefix all task endpoint paths with `/v2/`
   - `/tasks` → `/v2/tasks`
   - `/tasks/{id}` → `/v2/tasks/{id}`

2. **Update authentication**
   - Replace `X-Auth-Token` header with `Authorization: Bearer <token>`

3. **Update task ID handling**
   - Change from integer parsing to UUID string handling
   - Update any type-checking or validation logic

4. **Update task field names**
   - Replace all occurrences of `done` with `completed`
   - Update request bodies and response processing

5. **Add project_id to task creation**
   - Ensure `project_id` is included in every `POST /v2/tasks` request
   - Handle HTTP 422 error if omitted

6. **Implement pagination**
   - Update list endpoint consumers to handle the envelope format
   - Implement cursor-based pagination if needed
   - Use `items` array instead of processing bare array

7. **Update error handling**
   - Expect `project_id` validation errors (HTTP 422)
   - Expect `401 Unauthorized` if using old auth header

8. **Test thoroughly**
   - Test all workflows end-to-end
   - Verify paginated results load correctly across pages
   - Validate error paths

---

## Upgrade Command

Run this command to update the Zrb CLI globally:

```bash
npm install -g @zrb/cli@latest
```

For Yarn users:
```bash
yarn global add @zrb/cli@latest
```

Verify installation:
```bash
zrb --version
# Expected: v2.x.x
```
