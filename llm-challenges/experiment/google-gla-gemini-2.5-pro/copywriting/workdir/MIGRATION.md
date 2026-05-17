# Zrb API v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in Zrb API v2 and provides a step-by-step process for migrating your integration.

## Summary of Breaking Changes

- **Endpoint Paths**: All endpoints are now prefixed with `/v2/`.
- **Authentication**: Authentication now uses a `Bearer` token instead of `X-Auth-Token`.
- **Primary Key Type**: The `id` field on Task objects is now a UUID string, not an integer.
- **Field Rename**: The `done` field on Task objects has been renamed to `completed`.
- **List Pagination**: The `GET /tasks` endpoint now returns a paginated object instead of a bare array.
- **Task Creation**: Creating a task now requires a `project_id`.

---

## Breaking Changes in Detail

### 1. Endpoint Path Prefix

All API endpoints are now versioned with a `/v2/` prefix.

**Before (v1)**
```bash
GET /tasks
POST /tasks
GET /tasks/42
```

**After (v2)**
```bash
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 2. Authentication Header

API authentication has switched from a custom `X-Auth-Token` header to the standard `Authorization` header with a `Bearer` token.

**Before (v1)**
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.com/tasks
```

**After (v2)**
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.com/v2/tasks
```

### 3. Task ID Type Change (Integer to UUID)

The `id` field for tasks is now a UUID string. Your application must be able to store and handle UUIDs instead of integers for task identifiers.

**Before (v1)**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2)**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 4. Field Rename (`done` to `completed`)

The boolean field indicating a task's status has been renamed from `done` to `completed` for clarity.

**Before (v1)**
```bash
# Updating a task
curl -X PUT -d '{"done": true}' https://api.zrb.com/tasks/42
```

**After (v2)**
```bash
# Updating a task
curl -X PUT -d '{"completed": true}' https://api.zrb.com/v2/tasks/...
```

### 5. Paginated List Responses

The `GET /tasks` endpoint no longer returns a bare array of tasks. It now returns a paginated envelope containing the items and pagination metadata.

**Before (v1)**
```bash
# Request
GET /tasks

# Response Body
[
  {"id": 1, "title": "Buy milk", "done": false, ...},
  {"id": 2, "title": "Ship v1", "done": true, ...}
]
```

**After (v2)**
```bash
# Request
GET /v2/tasks

# Response Body
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, ...},
    {"id": "...", "title": "Ship v1", "completed": true, ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
You must now access the `items` key in the response to get the list of tasks. To fetch subsequent pages, use the `next_cursor` value.

### 6. Required `project_id` on Task Creation

The new `project_id` field is now required when creating a task.

**Before (v1)**
```bash
# Request Body
{
  "title": "New task title"
}
```

**After (v2)**
```bash
# Request Body
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

## Migration Checklist

Follow these steps to migrate your application to v2:

- [ ] **Database**: Update any database columns that store Task IDs from an integer type to a string/UUID type.
- [ ] **API Client**: Update the base URL for all API calls to include the `/v2/` prefix.
- [ ] **API Client**: Change the authentication header from `X-Auth-Token` to `Authorization: Bearer <token>`.
- [ ] **Code**: Update all references to the task `id` field to handle UUIDs.
- [ ] **Code**: Rename all references to the task `done` field to `completed`.
- [ ] **Code**: Update logic that lists tasks to handle the new paginated response envelope (i.e., access the `items` array). Implement cursor-based pagination if needed.
- [ ] **Code**: Add the `project_id` field to the request body for all task creation calls.

## Upgrade Command

To upgrade to the latest version of the Zrb CLI, run:

```bash
pip install --upgrade zrb
```
