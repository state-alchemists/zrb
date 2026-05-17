# Zrb Task API: v1 to v2 Migration Guide

Zrb v2 introduces projects, improved pagination, and stricter authentication. This guide outlines the breaking changes from v1 and how to update your existing integrations.

## Breaking Changes

### 1. Endpoint Prefix
All API routes are now prefixed with `/v2/`. Update all base URLs in your HTTP clients.

**Before (v1):**
```http
GET /tasks
```

**After (v2):**
```http
GET /v2/tasks
```

### 2. Authentication Method
The custom `X-Auth-Token` header has been replaced with the standard `Authorization: Bearer` scheme. Requests using the old header will receive an HTTP 401 Unauthorized response.

**Before (v1):**
```http
X-Auth-Token: <your_api_token>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task ID Type Change
Task identifiers have migrated from auto-incrementing integers to UUID strings. Ensure your database schemas, type definitions, and parsing logic can handle string IDs.

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

### 4. Task Schema: `done` renamed to `completed`
The boolean field representing a task's status has been renamed. This affects both the response objects and the payload when updating a task.

**Before (v1):**
```json
{
  "done": true
}
```

**After (v2):**
```json
{
  "completed": true
}
```

### 5. Task Creation Requires a Project
Tasks must now belong to a project. Creating a task without a `project_id` will result in an HTTP 422 Unprocessable Entity error.

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
The list endpoints no longer return a bare JSON array. They now return a paginated envelope containing `items`, `total`, and a `next_cursor` for fetching subsequent pages.

**Before (v1):**
```json
// Response from GET /tasks
[
  {"id": 1, "title": "Buy milk", "done": false}
]
```

**After (v2):**
```json
// Response from GET /v2/tasks
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123"}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Prepend `/v2` to all API request URLs.
- [ ] Update your HTTP client to use `Authorization: Bearer <token>` instead of `X-Auth-Token: <token>`.
- [ ] Update your code and database schemas to treat task `id` fields as UUID strings instead of integers.
- [ ] Search and replace references to the `done` field with `completed` in your codebase (for both reading responses and sending updates).
- [ ] Ensure all `POST /v2/tasks` requests include a valid `project_id` string in the request body.
- [ ] Refactor logic that handles list responses to access the array via the `.items` property instead of expecting a top-level array.
- [ ] Implement cursor-based pagination using the `next_cursor` response field where needed.

## Upgrade Command

To update your CLI to v2, run:

```bash
pip install --upgrade zrb
```