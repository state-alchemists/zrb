# Zrb API v2 Migration Guide

Zrb API v2 introduces projects, improved pagination, and stricter authentication. This guide outlines the breaking changes from v1 and provides a clear path to update your integrations. 

## Breaking Changes

### 1. Endpoint Prefix
All endpoints have been moved under the `/v2/` prefix to support API versioning.

**Before (v1)**
```http
GET /tasks
POST /tasks
```

**After (v2)**
```http
GET /v2/tasks
POST /v2/tasks
```

### 2. Authentication Header
The custom `X-Auth-Token` header has been replaced with the standard `Authorization` header using the `Bearer` scheme. Requests using the old header will receive an HTTP 401 response.

**Before (v1)**
```http
X-Auth-Token: <your_api_token>
```

**After (v2)**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task ID Data Type
Task IDs have been migrated from auto-incrementing integers to UUID strings to prevent enumeration and support distributed creation.

**Before (v1)**
```json
{
  "id": 42
}
```

**After (v2)**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Renamed Status Field
The `done` boolean field on the Task object has been renamed to `completed` across all endpoints (both in responses and when updating tasks).

**Before (v1)**
```json
{
  "title": "Write tests",
  "done": true
}
```

**After (v2)**
```json
{
  "title": "Write tests",
  "completed": true
}
```

### 5. Task Creation Requires Project ID
Tasks can no longer exist outside of a project. When creating a task, `project_id` is now a required field. Omitting it will result in an HTTP 422 response.

**Before (v1)**
```json
// POST /tasks
{
  "title": "New task title"
}
```

**After (v2)**
```json
// POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Responses
List endpoints no longer return a bare JSON array. They now return a paginated envelope containing an `items` array, a `total` count, and a `next_cursor` for fetching subsequent pages.

**Before (v1)**
```json
[
  {"id": 1, "title": "Buy milk", "done": false}
]
```

**After (v2)**
```json
{
  "items": [
    {"id": "a1b2c3d4...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123"}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

---

## Step-by-Step Migration Checklist

- [ ] Update all API request URLs to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` with `Authorization: Bearer` in your HTTP request headers.
- [ ] Update your database schemas and application types to expect string UUIDs for Task `id`s instead of integers.
- [ ] Rename the `done` field to `completed` in your models, UI bindings, and update payloads.
- [ ] Ensure your application supplies a valid `project_id` in the payload when calling `POST /v2/tasks`.
- [ ] Refactor code that calls `GET /v2/tasks` to read the `items` array from the response envelope and handle pagination using `next_cursor`.

## Upgrade Command

To update your local Zrb CLI to the latest v2 release, run:

```bash
npm install -g zrb@2
```