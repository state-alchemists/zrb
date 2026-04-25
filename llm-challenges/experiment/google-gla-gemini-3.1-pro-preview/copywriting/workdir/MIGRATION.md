# Zrb API v2 Migration Guide

## Overview

Welcome to v2! This release introduces projects, improved pagination, and stricter authentication. Several conventions have changed from v1, so we've put together this guide to help you upgrade your integrations smoothly.

## Breaking Changes

### 1. Endpoint URLs Prefixed with `/v2/`
All API endpoints have moved under the `/v2/` path.

**Before (v1):**
```http
GET /tasks
```

**After (v2):**
```http
GET /v2/tasks
```

### 2. Authentication Header Update
We've transitioned to standard Bearer token authentication. Requests using the old `X-Auth-Token` header will now return an HTTP 401 Unauthorized error.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task `id` Type is now UUID
Task identifiers have been changed from integers to UUID strings. You will need to update your data models and database schemas to accommodate this format.

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

### 4. Task Field `done` Renamed to `completed`
The field representing a task's status has been renamed to better reflect its meaning.

**Before (v1):**
```json
{
  "title": "Write tests",
  "done": false
}
```

**After (v2):**
```json
{
  "title": "Write tests",
  "completed": false
}
```

### 5. Task Creation Requires `project_id`
To support the new projects feature, you must now provide a `project_id` when creating a new task. Omitting it will return an HTTP 422 Unprocessable Entity error.

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
The `GET /v2/tasks` endpoint now returns a paginated envelope object instead of a bare JSON array. You can use the `cursor` query parameter to fetch subsequent pages (e.g., `?cursor=<next_cursor>`).

**Before (v1):**
```json
[
  {
    "id": 1,
    "title": "Buy milk",
    "done": false,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

**After (v2):**
```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Buy milk",
      "completed": false,
      "project_id": "proj_abc123",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Change the authentication header from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Update your database schemas and code types to treat task `id` as a UUID string (instead of an integer).
- [ ] Find and replace all references to the `done` field with `completed`.
- [ ] Update task creation payloads (`POST /v2/tasks`) to include a valid `project_id`.
- [ ] Adjust your response parsing logic for list endpoints (`GET /v2/tasks`) to extract the `items` array and handle the new `next_cursor` for pagination.

## Upgrade Command

Ready to make the jump? Upgrade your local CLI to v2 by running:

```bash
zrb upgrade
```