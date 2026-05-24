# Zrb CLI v1 to v2 Migration Guide

This guide details the breaking changes and new features introduced in Zrb CLI v2, and provides a step-by-step process for migrating your existing v1 integrations.

## What's New in v2

Zrb CLI v2 introduces significant improvements including support for projects, enhanced pagination capabilities, and a more robust authentication mechanism. These changes aim to provide a more scalable and feature-rich experience.

---

## Breaking Changes

Zrb CLI v2 introduces several breaking changes that require updates to your existing code. Each change is detailed below with before-and-after examples.

### 1. Endpoint Path Prefix

All API endpoints are now prefixed with `/v2/`. This ensures versioning and allows for parallel development of future API versions.

**v1 Example:**
```bash
curl -X GET "https://api.zrb.com/tasks" \
  -H "X-Auth-Token: <your_api_key>"
```

**v2 Example:**
```bash
curl -X GET "https://api.zrb.com/v2/tasks" \
  -H "Authorization: Bearer <your_api_token>"
```

### 2. Authentication Header

The authentication header has changed from `X-Auth-Token` to a standard `Authorization: Bearer` token. Requests using the old header will receive an HTTP 401 Unauthorized response.

**v1 Example:**
```bash
-H "X-Auth-Token: <your_api_key>"
```

**v2 Example:**
```bash
-H "Authorization: Bearer <your_api_token>"
```

### 3. Task ID Type Change

The `id` field for Task objects, previously an integer, is now a UUID string. This change provides greater uniqueness and flexibility for task identification.

**v1 Example (Get Task):**
```bash
curl -X GET "https://api.zrb.com/tasks/42" \
  -H "X-Auth-Token: <your_api_key>"
```

**v2 Example (Get Task):**
```bash
curl -X GET "https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer <your_api_token>"
```

### 4. Task Field Renamed: `done` to `completed`

The boolean field `done` within the Task object, indicating completion status, has been renamed to `completed`.

**v1 Example (Update Task):**
```bash
curl -X PUT "https://api.zrb.com/tasks/42" \
  -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"done": true}'
```

**v2 Example (Update Task):**
```bash
curl -X PUT "https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

### 5. Task Creation Requires `project_id`

When creating a new task, the `project_id` field is now a mandatory string. Omitting it will result in an HTTP 422 Unprocessable Entity error.

**v1 Example (Create Task):**
```bash
curl -X POST "https://api.zrb.com/tasks" \
  -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task title"}'
```

**v2 Example (Create Task):**
```bash
curl -X POST "https://api.zrb.com/v2/tasks" \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task title", "project_id": "proj_abc123"}'
```

### 6. List Endpoints Return Paginated Envelope

All list endpoints (e.g., `GET /v2/tasks`) now return a paginated envelope object instead of a bare array of items. This envelope includes `items` (the list of tasks), `total` (total number of items), and `next_cursor` for pagination.

**v1 Example Response (List Tasks):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**v2 Example Response (List Tasks):**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-f6e7-8901-bcde-f12345678901", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page in v2, append `?cursor=<next_cursor>` to your request. You can also use the `limit` query parameter to control the number of results per page (default 20).

## Migration Checklist

Follow these steps to migrate your Zrb CLI integrations from v1 to v2:

1.  **Update Endpoint Paths**: Prefix all Zrb API endpoint paths with `/v2/`.
2.  **Change Authentication Header**: Replace `X-Auth-Token` with `Authorization: Bearer <your_api_token>`.
3.  **Adjust Task ID Handling**: Update any code that expects integer task IDs to handle UUID strings instead.
4.  **Rename `done` to `completed`**: Update all references to the `done` field in Task objects to `completed`.
5.  **Provide `project_id` on Task Creation**: Ensure all `POST /v2/tasks` requests include a valid `project_id` in the request body.
6.  **Adapt to Paginated Responses**: Modify code that processes list endpoint responses to parse the new paginated envelope structure, accessing items via the `items` field and handling `next_cursor` for pagination.

## Upgrade Command

To upgrade your Zrb CLI installation to v2, run the following command:

```bash
zrb upgrade
```