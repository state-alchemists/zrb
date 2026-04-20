# Zrb CLI v2 Migration Guide

Welcome to Zrb CLI v2! This release introduces projects, improved pagination, and stricter authentication. To accommodate these improvements, we've made several breaking changes to the Task API. 

This guide outlines every breaking change and provides a step-by-step checklist to help you upgrade smoothly.

## Breaking Changes

### 1. API Endpoint Prefix
All API endpoints have been moved under the `/v2/` prefix to support API versioning.

**Before (v1):**
```http
GET /tasks
```

**After (v2):**
```http
GET /v2/tasks
```

### 2. Authentication Header
The custom `X-Auth-Token` header has been replaced with the standard `Authorization: Bearer` scheme. Using the old header will now return an `HTTP 401 Unauthorized` error.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task ID Format
Task `id` fields have changed from auto-incrementing integers to UUID strings. Ensure your application schema and database can handle strings for task IDs.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

### 4. Status Field Renamed
The boolean field representing a task's completion status has been renamed from `done` to `completed`. This affects both the task representation and the payload for updating tasks.

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

### 5. Task Creation Requires Project ID
Creating a new task now explicitly requires a `project_id`. Omitting this field in a POST request will result in an `HTTP 422 Unprocessable Entity` error.

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
The `GET /v2/tasks` endpoint no longer returns a bare JSON array. It now returns a paginated envelope object. To iterate through results, use the `?cursor=<next_cursor>` query parameter.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2c3d4...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123"},
    {"id": "e5f67890...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123"}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Step-by-Step Migration Checklist

- [ ] Update all API base URLs to append the `/v2/` prefix.
- [ ] Replace `X-Auth-Token: <token>` with `Authorization: Bearer <token>` in your HTTP client's default headers.
- [ ] Update your data models and database schemas to treat task `id`s as UUID strings instead of integers.
- [ ] Search and replace references of the `done` field with `completed` across your task objects and update payloads.
- [ ] Update all task creation (`POST`) workflows to include a valid `project_id`.
- [ ] Refactor your list-fetching logic to extract arrays from the `items` property of the new response envelope, and implement cursor-based pagination.
- [ ] Test all CRUD operations against the v2 endpoints.

## Upgrade Command

To update your Zrb CLI to the latest version, run:

```bash
zrb upgrade
```