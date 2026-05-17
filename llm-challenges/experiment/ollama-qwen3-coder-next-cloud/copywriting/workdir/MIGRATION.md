# Zrb CLI v1 to v2 Migration Guide

This guide helps experienced Zrb v1 users migrate to v2. v2 introduces breaking changes in authentication, endpoint structure, data types, and pagination. This guide covers all changes explicitly with before/after examples.

---

## Breaking Changes Summary

| # | Change | Impact |
|---|--------|--------|
| 1 | All endpoints prefixed with `/v2/` | URL paths must change |
| 2 | Authentication header changed | `X-Auth-Token` → `Authorization: Bearer` |
| 3 | Task `id` type changed | Integer → UUID string |
| 4 | Task field `done` renamed | `done` → `completed` |
| 5 | Task creation requires `project_id` | New required field |
| 6 | List endpoints return paginated envelope | Response structure changed |

---

## 1. Endpoint URL Changes

**Change:** All endpoints now require the `/v2/` prefix.

### Before (v1)
```bash
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

### After (v2)
```bash
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication Header

**Change:** `X-Auth-Token` header replaced with `Authorization: Bearer` format.

### Before (v1)
```bash
curl -X GET https://api.zrb.sh/tasks \
  -H "X-Auth-Token: your_v1_api_key"
```

### After (v2)
```bash
curl -X GET https://api.zrb.sh/v2/tasks \
  -H "Authorization: Bearer your_v2_api_token"
```

Requests with the old `X-Auth-Token` header will receive HTTP 401 Unauthorized.

---

## 3. Task ID Type Change

**Change:** Task IDs are now UUID strings instead of integers.

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

**Impact:** Code that parses or constructs task IDs must handle UUID strings. String comparison and formatting will differ.

---

## 4. Field Renaming: `done` → `completed`

**Change:** The boolean field `done` was renamed to `completed`.

### Before (v1)
```json
PUT /tasks/42
{
  "done": true
}
```

### After (v2)
```json
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
{
  "completed": true
}
```

Using `done` in v2 requests will be ignored; use `completed` instead.

---

## 5. Required `project_id` on Task Creation

**Change:** Creating a task now requires a `project_id` field. Omitting it returns HTTP 422 Unprocessable Entity.

### Before (v1)
```json
POST /tasks
{
  "title": "New task"
}
```
**Response:** Created task (HTTP 201)

### After (v2)
```json
POST /v2/tasks
{
  "title": "New task",
  "project_id": "proj_abc123"
}
```
**Response:** Created task (HTTP 201)

**Without `project_id`:**
```json
422 Unprocessable Entity
{
  "error": "project_id is required"
}
```

---

## 6. Paginated List Response

**Change:** List endpoints now return a paginated envelope with `items`, `total`, and `next_cursor` fields instead of a bare array.

### Before (v1)
```bash
curl https://api.zrb.sh/tasks
```
```json
[
  {"id": 1, "title": "Task 1", "done": false},
  {"id": 2, "title": "Task 2", "done": true}
]
```

### After (v2)
```bash
curl "https://api.zrb.sh/v2/tasks?limit=20"
```
```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Task 1",
      "completed": false
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "title": "Task 2",
      "completed": true
    }
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

### Pagination Example

**First page:**
```bash
curl "https://api.zrb.sh/v2/tasks?limit=10"
```

**Next page using `next_cursor`:**
```bash
curl "https://api.zrb.sh/v2/tasks?limit=10&cursor=cursor_xyz"
```

---

## Step-by-Step Migration Checklist

Use this checklist to systematically migrate your codebase:

1. **Update API URLs**
   - [ ] Replace all `/tasks` endpoints with `/v2/tasks`
   - [ ] Replace all `/tasks/{id}` endpoints with `/v2/tasks/{uuid}`

2. **Update Authentication**
   - [ ] Replace `X-Auth-Token: <key>` header with `Authorization: Bearer <token>`
   - [ ] Update token storage/retrieval logic (API tokens may differ between v1/v2)
   - [ ] Verify token permissions in v2 dashboard

3. **Handle Task ID Changes**
   - [ ] Update any code expecting integer task IDs to handle UUID strings
   - [ ] Update regex patterns, database schemas, or serialization logic
   - [ ] Test ID parsing and formatting with UUID examples

4. **Update Request Bodies**
   - [ ] Replace `done` field with `completed` in PUT/POST requests
   - [ ] Add `project_id` to all task creation requests (POST `/v2/tasks`)

5. **Implement Pagination**
   - [ ] Update list response parsing to handle `items`, `total`, `next_cursor`
   - [ ] Replace array iteration with envelope unwrapping
   - [ ] Add cursor pagination logic for iterating beyond first page
   - [ ] Consider adding a pagination abstraction layer

6. **Update Error Handling**
   - [ ] Handle HTTP 422 for missing `project_id` on task creation
   - [ ] Update tests to expect paginated envelope structure
   - [ ] Handle 401 for incorrect authentication headers

7. **Test Thoroughly**
   - [ ] Test CRUD operations with new v2 format
   - [ ] Verify pagination works across multiple pages
   - [ ] Confirm authentication works with new header format
   - [ ] Validate UUID-based IDs in your system

8. **Deploy and Monitor**
   - [ ] Deploy updated code to staging
   - [ ] Monitor for authentication (401) and validation (422) errors in logs
   - [ ] Verify no code paths still use old v1 endpoints

---

## Run the Upgrade Command

To install the latest v2 CLI and authenticate:

```bash
npm install -g @zrb/cli@latest && zrb upgrade
```

After installation, reconfigure your API token:

```bash
zrb configure --token YOUR_V2_API_TOKEN
```

For support, visit https://docs.zrb.sh/migration or contact developer support.
