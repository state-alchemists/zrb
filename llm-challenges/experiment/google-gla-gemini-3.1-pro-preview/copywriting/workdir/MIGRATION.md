# Zrb Task API v2 Migration Guide

Welcome to Zrb CLI v2! This release introduces project organization, improved pagination, and enhanced security. It also includes several breaking changes from v1. 

This guide outlines every breaking change and provides a step-by-step checklist to help you upgrade your applications.

## Breaking Changes

### 1. Endpoint URL Prefix
All API endpoints have moved from the root path to a `/v2/` prefix.

**Before (v1):**
```http
GET /tasks
```

**After (v2):**
```http
GET /v2/tasks
```

### 2. Authentication Header
The custom `X-Auth-Token` header has been deprecated. You must now use the standard `Authorization` header with a Bearer token. Using the old header will result in an `HTTP 401 Unauthorized` error.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_key>
```

### 3. Task IDs are now UUIDs
The task `id` field has changed from an auto-incrementing integer to a UUID string. All path parameters for getting, updating, or deleting tasks must now use UUIDs.

**Before (v1):**
```json
{
  "id": 42
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Task Field `done` renamed to `completed`
The boolean flag indicating whether a task is finished has been renamed for clarity.

**Before (v1):**
```json
{
  "title": "Write tests",
  "done": true
}
```

**After (v2):**
```json
{
  "title": "Write tests",
  "completed": true
}
```

### 5. `project_id` is Required for Creation
Tasks can no longer be orphaned; they must belong to a project. When creating a task, `project_id` is now a required string. Omitting it will result in an `HTTP 422 Unprocessable Entity` error.

**Before (v1):**
```json
// POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**
```json
// POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Responses
Endpoints that return multiple tasks no longer return a bare array. They now return a paginated envelope object. To access the data, read the `items` array.

**Before (v1):**
```json
// GET /tasks
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."}
]
```

**After (v2):**
```json
// GET /v2/tasks
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update your base API URLs or client configurations to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` with `Authorization: Bearer <token>` in your HTTP client requests.
- [ ] Update your database schemas, ORM models, and type definitions (e.g., TypeScript interfaces) to expect UUID strings instead of integers for task IDs.
- [ ] Search and replace all references of the `done` property to `completed` in your models, request payloads, and UI templates.
- [ ] Update task creation logic to supply a valid `project_id` when calling `POST /v2/tasks`.
- [ ] Refactor response parsing for list endpoints (like `GET /v2/tasks`) to extract data from `response.items` instead of treating the root response as an array.
- [ ] Implement pagination in your UI or data fetchers using the new `next_cursor` property.

## Upgrade Command

To update to the latest CLI version, run:

```bash
pip install --upgrade zrb
```