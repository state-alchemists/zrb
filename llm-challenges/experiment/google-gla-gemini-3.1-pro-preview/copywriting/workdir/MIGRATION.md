# Zrb Task API v1 to v2 Migration Guide

Zrb v2 introduces project grouping, cursor-based pagination, and standard Bearer token authentication. This guide details the breaking changes to the API and outlines how to update your integration.

## Breaking Changes

### 1. Base URL Prefix
All API endpoints are now explicitly versioned and prefixed with `/v2/`.

**Before**
```http
GET /tasks
```

**After**
```http
GET /v2/tasks
```

### 2. Authentication Scheme
The custom header `X-Auth-Token` has been removed. You must now use standard `Authorization: Bearer` syntax. Sending the old header will result in an HTTP 401 error.

**Before**
```http
X-Auth-Token: <your_api_token>
```

**After**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task Schema Updates
The task object structure has three significant changes:
* `id` changed from an integer to a UUID string.
* `done` was renamed to `completed`.
* `project_id` is newly exposed on the object.

**Before**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 4. Required Project ID on Task Creation
When creating a task, you can no longer pass just a title. `project_id` is strictly required. Omitting it will return an HTTP 422 error.

**Before**
```json
// POST /tasks
{
  "title": "New task title"
}
```

**After**
```json
// POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 5. Paginated List Responses
List endpoints (`GET /v2/tasks`) no longer return bare JSON arrays. They return a paginated envelope object. Your code must extract the data from the `items` property.

**Before**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."}
]
```

**After**
```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
*(To fetch the next page, append the cursor to the URL: `GET /v2/tasks?cursor=cursor_xyz`)*

---

## Migration Checklist

- [ ] Update all endpoint URLs to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token: <token>` headers with `Authorization: Bearer <token>`.
- [ ] Update variables, types, and database schemas handling task `id`s to expect UUID strings rather than integers.
- [ ] Rename property lookups and updates from `done` to `completed` across your codebase.
- [ ] Update your task creation logic (`POST /v2/tasks`) to include a valid `project_id` in the payload.
- [ ] Adjust response parsing for list endpoints to iterate over `response.items` instead of the root array, and implement pagination using `next_cursor`.

## Upgrade Command

To update the Zrb CLI to the latest v2 release, run:

```bash
zrb upgrade
```