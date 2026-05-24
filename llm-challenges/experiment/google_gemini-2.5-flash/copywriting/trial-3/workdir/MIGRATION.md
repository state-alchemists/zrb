# Zrb CLI v1 to v2 Migration Guide

This guide details the breaking changes and necessary steps to migrate your existing Zrb CLI integrations from v1 to v2. Version 2 introduces significant improvements, including project support and enhanced authentication, but requires updates to your API calls.

## Key Breaking Changes

### 1. Endpoint Prefix Change: `/tasks` to `/v2/tasks`

All API endpoints are now prefixed with `/v2/`. This ensures versioning clarity and allows for future API evolution.

**Before (v1):**
```
GET /tasks
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

### 2. Authentication Header Update

The authentication mechanism has changed from a custom `X-Auth-Token` header to a standard Bearer token. Requests using the old header will result in an HTTP 401 Unauthorized error.

**Before (v1):**
```
X-Auth-Token: <your_api_key>
```

**After (v2):**
```
Authorization: Bearer <your_api_token>
```

### 3. Task ID Type Change: Integer to UUID String

The `id` field for Task objects has transitioned from an integer to a UUID string. This provides greater uniqueness and extensibility.

**Before (v1 - Task Object Example):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2 - Task Object Example):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

This change affects `GET /v2/tasks/{id}`, `PUT /v2/tasks/{id}`, and `DELETE /v2/tasks/{id}` where the `{id}` in the URL path must now be a UUID string.

### 4. Task Field Rename: `done` to `completed`

The boolean field indicating a task's completion status has been renamed from `done` to `completed`.

**Before (v1 - Update Task Request Body):**
```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2 - Update Task Request Body):**
```json
{
  "title": "Updated title",
  "completed": true
}
```

### 5. Task Creation Requires `project_id`

In v2, creating a new task now requires associating it with a `project_id`. Omitting this field will result in an HTTP 422 Unprocessable Entity error.

**Before (v1 - Create Task Request Body):**
```json
{
  "title": "New task title"
}
```

**After (v2 - Create Task Request Body):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. List Endpoints Return a Paginated Envelope

All list endpoints, such as `GET /v2/tasks`, now return a paginated envelope object instead of a bare array of items. This new structure facilitates efficient data retrieval for large collections.

**Before (v1 - List Tasks Response):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2 - List Tasks Response):**
```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v2", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch subsequent pages, include the `cursor` query parameter from the `next_cursor` field in the response: `GET /v2/tasks?cursor=cursor_xyz`.

## Migration Checklist

To ensure a smooth transition to Zrb CLI v2, follow these steps:

1.  **Update Endpoint Paths**: Prefix all Zrb API endpoint calls with `/v2/`.
2.  **Migrate Authentication**: Change `X-Auth-Token` headers to `Authorization: Bearer <your_api_token>`.
3.  **Handle Task IDs**: Update your code to expect and provide UUID strings for task IDs instead of integers.
4.  **Rename `done` to `completed`**: Adjust all references to the task completion status field.
5.  **Provide `project_id`**: Ensure all new task creation requests include a valid `project_id`.
6.  **Parse Paginated Responses**: Modify your parsing logic for list endpoints to handle the new `{"items": [], "total": 0, "next_cursor": ""}` envelope. Implement pagination logic using the `cursor` query parameter.

## Upgrade Command

To upgrade your Zrb CLI installation:

```bash
zrb upgrade --to v2
```