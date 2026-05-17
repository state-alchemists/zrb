# Zrb CLI v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in Zrb CLI v2 and provides a step-by-step process for migrating your existing v1 implementations to the new API. Zrb CLI v2 brings significant improvements, including project support, enhanced pagination, and stricter authentication.

## Breaking Changes

### 1. API Endpoint Prefix

All Zrb CLI API endpoints in v2 are now prefixed with `/v2/`. This means you must update all your API request paths.

**Before (v1):**
```bash
curl -X GET https://api.zrb.dev/tasks
```

**After (v2):**
```bash
curl -X GET https://api.zrb.dev/v2/tasks
```

### 2. Authentication Header Change

The authentication mechanism has been updated for improved security. The `X-Auth-Token` header is no longer supported. You must now use a `Bearer` token in the `Authorization` header.

**Before (v1):**
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.dev/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.dev/v2/tasks
```

### 3. Task `id` Type Changed to UUID String

The `id` field for Task objects has changed from an integer to a UUID string. This impacts how you store, retrieve, and reference tasks.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.dev/tasks/42
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 4. Task Field `done` Renamed to `completed`

The boolean field `done` within the Task object has been renamed to `completed` for better clarity.

**Before (v1):**
```json
{
  "title": "Review code",
  "done": true
}
```
```bash
curl -X PUT -H "X-Auth-Token: <your_api_key>" -H "Content-Type: application/json" -d '{"done": true}' https://api.zrb.dev/tasks/42
```

**After (v2):**
```json
{
  "title": "Review code",
  "completed": true
}
```
```bash
curl -X PUT -H "Authorization: Bearer <your_api_token>" -H "Content-Type: application/json" -d '{"completed": true}' https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 5. Task Creation Now Requires `project_id`

When creating a new task, the `project_id` field is now mandatory. Omitting this field will result in an HTTP 422 error.

**Before (v1):**
```json
{
  "title": "New task title"
}
```
```bash
curl -X POST -H "X-Auth-Token: <your_api_key>" -H "Content-Type: application/json" -d '{"title": "New task title"}' https://api.zrb.dev/tasks
```

**After (v2):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```
```bash
curl -X POST -H "Authorization: Bearer <your_api_token>" -H "Content-Type: application/json" -d '{"title": "New task title", "project_id": "proj_abc123"}' https://api.zrb.dev/v2/tasks
```

### 6. List Endpoints Return a Paginated Envelope

All list endpoints (e.g., `/tasks`) now return a paginated envelope object instead of a bare array of task objects. This envelope includes `items`, `total`, and `next_cursor` fields.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "..."},
  {"id": 2, "title": "Ship v1", "done": true, "..."}
]
```
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.dev/tasks
```

**After (v2):**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "..."},
    {"id": "uuid-2", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.dev/v2/tasks?limit=1&cursor=cursor_xyz
```

## Migration Checklist

1.  **Update API Endpoints:** Change all API endpoint paths to include the `/v2/` prefix.
2.  **Modify Authentication:** Switch from `X-Auth-Token` header to `Authorization: Bearer <your_api_token>` for all requests.
3.  **Refactor Task IDs:** Update any code that stores or processes Task IDs to handle UUID strings instead of integers.
4.  **Rename `done` to `completed`:** Replace all references to the `done` field with `completed` in your Task object handling logic.
5.  **Add `project_id` for Task Creation:** Ensure all Task creation requests include a valid `project_id` in the request body.
6.  **Adjust List Endpoint Parsing:** Modify your code to parse the new paginated envelope structure for list responses, accessing tasks via the `items` array. Implement pagination logic using `cursor` and `limit` query parameters.

## Upgrade Command

To upgrade your Zrb CLI to the latest version, run:

```bash
zrb upgrade --version v2
```
