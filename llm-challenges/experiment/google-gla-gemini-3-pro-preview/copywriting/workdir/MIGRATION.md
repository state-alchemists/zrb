# Zrb API v1 to v2 Migration Guide

Zrb API v2 introduces projects, improved pagination, and stricter authentication. To accommodate these features, several v1 fields and conventions have been modified or removed. 

This guide details the breaking changes and provides a step-by-step checklist to upgrade your integration.

## Breaking Changes

### 1. API Endpoint Prefix
All API routes are now prefixed with `/v2/` to ensure safe versioning. 

**Before:**
```http
GET /tasks
POST /tasks
```

**After:**
```http
GET /v2/tasks
POST /v2/tasks
```

### 2. Authentication Header
The custom `X-Auth-Token` header has been replaced with the standard `Authorization: Bearer` scheme. Requests using the old header will receive an `HTTP 401 Unauthorized` response.

**Before:**
```http
X-Auth-Token: <your_api_token>
```

**After:**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task ID Data Type
Task identifiers have migrated from sequential integers to globally unique UUID strings. Ensure your database schemas, variables, and type definitions treat IDs as strings.

**Before:**
```json
{
  "id": 42
}
```

**After:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Task Completion Field Renamed
The boolean field representing a task's status has been renamed from `done` to `completed`. This affects both the JSON responses you receive and the payloads you send (e.g., during `PUT` requests).

**Before:**
```json
{
  "title": "Write tests",
  "done": true
}
```

**After:**
```json
{
  "title": "Write tests",
  "completed": true
}
```

### 5. Project ID is Required for Creation
Tasks are now scoped to projects. When creating a new task via `POST /v2/tasks`, you must provide a valid `project_id`. Omitting it will result in an `HTTP 422 Unprocessable Entity` error.

**Before:**
```json
{
  "title": "New task title"
}
```

**After:**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. List Endpoints Use Paginated Envelopes
List endpoints (`GET /v2/tasks`) no longer return a bare JSON array. They now return a paginated envelope object containing `items`, `total`, and a `next_cursor` for fetching subsequent pages.

**Before:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false}
]
```

**After:**
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

---

## Migration Checklist

Follow these steps to safely migrate your application to v2:

- [ ] **Update Type Definitions:** Change your `Task` models/types. Update `id` to be a string, rename `done` to `completed` (boolean), and add `project_id` (string).
- [ ] **Update Authentication:** Replace all `X-Auth-Token` headers in your HTTP clients with `Authorization: Bearer <token>`.
- [ ] **Update URLs:** Prepend `/v2` to all Zrb API endpoint URLs.
- [ ] **Fix Task Creation:** Ensure your task creation workflows fetch or store a `project_id`, and include it in all `POST /v2/tasks` payloads.
- [ ] **Fix Task Updates:** Audit all `PUT` requests to ensure they send `completed` instead of `done`.
- [ ] **Handle Pagination:** Refactor responses from `GET /v2/tasks` to read from `response.items` instead of the root response. Implement cursor-based pagination using the `next_cursor` property if fetching multiple pages.
- [ ] **Run Tests:** Execute your integration tests against the v2 endpoints.

## Upgrade Command

To update the Zrb CLI on your system to the latest v2 release, run:

```bash
pip install --upgrade "zrb>=2.0.0"
```