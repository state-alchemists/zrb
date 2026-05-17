# Zrb CLI API: v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in the Zrb CLI API v2 and provides a step-by-step process for migrating your integration. V2 introduces new features like projects, cursor-based pagination, and a more robust authentication scheme.

## Summary of Breaking Changes

1.  **Endpoint Path Prefix**: All endpoints are now prefixed with `/v2/`.
2.  **Authentication**: The `X-Auth-Token` header is replaced by the `Authorization: Bearer <token>` standard.
3.  **Task ID Type**: The `id` field on Task objects is now a UUID string instead of an integer.
4.  **Field Rename**: The `done` field in the Task object has been renamed to `completed`.
5.  **Task Creation**: Creating a task now requires a `project_id`.
6.  **List Responses**: Endpoints that return a list of items are now wrapped in a pagination envelope.

---

## Detailed Breaking Changes

### 1. Endpoint Path Prefix

All API endpoints are now versioned with a `/v2/` prefix.

**Before (v1):**
```
GET /tasks
POST /tasks
PUT /tasks/{id}
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/{id}
```

### 2. Authentication Header

Authentication is now done via a Bearer token in the `Authorization` header, which is more conventional.

**Before (v1):**
```http
GET /tasks
Host: api.zrb.com
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
GET /v2/tasks
Host: api.zrb.com
Authorization: Bearer <your_api_token>
```

### 3. Task ID Type Change

The `id` field for tasks has been changed from an `integer` to a `UUID string` to ensure global uniqueness.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 4. Field Rename: `done` to `completed`

The boolean field indicating a task's status has been renamed for clarity.

**Before (v1):**
`PUT /tasks/42`
```json
{
  "done": true
}
```

**After (v2):**
`PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890`
```json
{
  "completed": true
}
```

### 5. Task Creation Requires `project_id`

With the introduction of Projects, every task must be associated with a project upon creation.

**Before (v1):**
`POST /tasks`
```json
{
  "title": "New task title"
}
```

**After (v2):**
`POST /v2/tasks`
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Responses

The `GET /tasks` endpoint no longer returns a bare array. It now returns a paginated object containing the items and metadata for fetching subsequent pages.

**Before (v1):**
`GET /tasks`
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
`GET /v2/tasks`
```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, ...},
    {"id": "b2c3...", "title": "Ship v1", "completed": true, ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
To fetch the next page, your application will need to use the `next_cursor` value:
`GET /v2/tasks?cursor=cursor_xyz`

---

## Migration Checklist

Follow these steps to update your application for v2 compatibility:

- [ ] Update all API endpoint URLs to include the `/v2/` prefix.
- [ ] Change the authentication header from `X-Auth-Token` to `Authorization: Bearer <token>`.
- [ ] Update any code that handles task IDs to expect a UUID string instead of an integer. This may affect database schemas, variable types, and client-side routing.
- [ ] Rename all instances of the `done` field to `completed` when reading or updating tasks.
- [ ] Modify the "create task" functionality to include the required `project_id` field.
- [ ] Adjust the logic for listing tasks to handle the new paginated response envelope. Your code must now access the tasks via the `items` key and implement logic to follow the `next_cursor` for full data retrieval.

## Upgrade Command

To upgrade to the latest version of the Zrb CLI, run:

```bash
zrb upgrade --version=v2
```
