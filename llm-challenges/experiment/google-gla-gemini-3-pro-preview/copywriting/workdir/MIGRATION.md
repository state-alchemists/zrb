# Zrb v2 Migration Guide

Zrb v2 introduces projects, improved pagination, and stricter authentication. To accommodate these features, the v2 API includes several breaking changes from v1. 

This guide details what has changed and how to update your integration.

## Breaking Changes

### 1. Endpoint Prefix
All API endpoints are now prefixed with `/v2/`.

**Before**
```http
GET /tasks
```

**After**
```http
GET /v2/tasks
```

### 2. Authentication Header
The authentication header has moved to the standard Bearer token format. Requests using the old header will be rejected with an `HTTP 401 Unauthorized` status.

**Before**
```http
X-Auth-Token: <your_api_key>
```

**After**
```http
Authorization: Bearer <your_api_key>
```

### 3. Task ID Type Changed to UUID
Task IDs have migrated from integers to UUID strings to better support uniqueness across systems. Ensure your databases and type definitions reflect this change.

**Before**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**After**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

### 4. `done` Field Renamed to `completed`
The boolean flag indicating a task's status has been renamed for clarity.

**Before**
```json
{
  "title": "Write tests",
  "done": false
}
```

**After**
```json
{
  "title": "Write tests",
  "completed": false
}
```

### 5. `project_id` Required for Task Creation
Zrb v2 introduces project grouping. When creating a new task, you must now specify a valid `project_id`. Omitting it will result in an `HTTP 422 Unprocessable Entity` error.

**Before**
```http
POST /tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

**After**
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated Envelope for List Endpoints
List endpoints (like `GET /v2/tasks`) no longer return a bare JSON array. They now return a pagination envelope containing an `items` array, total count, and a cursor for fetching the next page.

**Before**
```json
[
  { 
    "id": 1, 
    "title": "Buy milk", 
    "done": false 
  }
]
```

**After**
```json
{
  "items": [
    { 
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", 
      "title": "Buy milk", 
      "completed": false, 
      "project_id": "proj_abc123" 
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update base URLs for all endpoints to prepend `/v2/`.
- [ ] Change the authentication header from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Update your data structures and database schemas to store task `id`s as UUID strings instead of integers.
- [ ] Rename the `done` field to `completed` in your code (especially in `PUT` requests and when reading responses).
- [ ] Update your task creation logic (`POST /v2/tasks`) to always include a `project_id`.
- [ ] Refactor responses from list endpoints to read from the `.items` property instead of iterating directly over the root array.
- [ ] Implement pagination parsing using the `next_cursor` parameter for robust data fetching.

## Upgrade

Ready to make the switch? Run the following command to upgrade:

```bash
zrb upgrade
```