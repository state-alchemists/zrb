# Zrb CLI v2 Migration Guide

This guide details the breaking changes introduced in Zrb CLI v2 and provides a clear path for migrating your existing v1 implementations.

## Introduction to v2

Zrb CLI v2 brings significant improvements, including project support, enhanced pagination, and a more robust authentication mechanism. To accommodate these features, several API conventions and data structures have been updated.

## Breaking Changes

### 1. API Endpoint Prefix

All API endpoints in v2 are now prefixed with `/v2/`. This ensures versioning and allows for future API evolution.

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

**Example (List Tasks):**

Before (v1):
```bash
curl -H "X-Auth-Token: <your_api_key>" \
  https://api.zrb.com/tasks
```

After (v2):
```bash
curl -H "Authorization: Bearer <your_api_token>" \
  https://api.zrb.com/v2/tasks
```

### 2. Authentication Header Change

The authentication mechanism has been updated to use a standard Bearer token. The `X-Auth-Token` header is no longer supported and will result in an `HTTP 401 Unauthorized` response.

**Before (v1):**
```
X-Auth-Token: <your_api_key>
```

**After (v2):**
```
Authorization: Bearer <your_api_token>
```

**Example (Get Task):**

Before (v1):
```bash
curl -H "X-Auth-Token: <your_api_key>" \
  https://api.zrb.com/tasks/42
```

After (v2):
```bash
curl -H "Authorization: Bearer <your_api_token>" \
  https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 3. Task `id` Type Changed from Integer to UUID String

Task identifiers are now universally unique identifiers (UUIDs) instead of integers. This change impacts all endpoints that reference tasks by their `id`.

**Before (v1) Task Object:**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2) Task Object:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Example (Get Task by ID):**

Before (v1):
```bash
curl -H "X-Auth-Token: <your_api_key>" \
  https://api.zrb.com/tasks/42
```

After (v2):
```bash
curl -H "Authorization: Bearer <your_api_token>" \
  https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 4. Task Field `done` Renamed to `completed`

The boolean field indicating a task's completion status has been renamed from `done` to `completed`. This change affects task creation and update operations.

**Before (v1) Update Task Request Body:**
```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2) Update Task Request Body:**
```json
{
  "title": "Updated title",
  "completed": true
}
```

**Example (Update Task):**

Before (v1):
```bash
curl -X PUT -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"done": true}' \
  https://api.zrb.com/tasks/42
```

After (v2):
```bash
curl -X PUT -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}' \
  https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 5. Task Creation Now Requires `project_id`

All new tasks must now be associated with a `project_id`. Omitting this field during task creation will result in an `HTTP 422 Unprocessable Entity` error.

**Before (v1) Create Task Request Body:**
```json
{
  "title": "New task title"
}
```

**After (v2) Create Task Request Body:**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Example (Create Task):**

Before (v1):
```bash
curl -X POST -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Plan migration guide"}' \
  https://api.zrb.com/tasks
```

After (v2):
```bash
curl -X POST -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Plan migration guide", "project_id": "proj_docs_team"}' \
  https://api.zrb.com/v2/tasks
```

### 6. List Endpoints Return a Paginated Envelope

List endpoints (e.g., `GET /v2/tasks`) no longer return a bare array of task objects. Instead, they return a paginated envelope containing `items`, `total`, and `next_cursor` fields.

**Before (v1) List Tasks Response:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) List Tasks Response:**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false, "project_id": "proj-a", "created_at": "..."},
    {"id": "uuid-2", "title": "Ship v1", "completed": true, "project_id": "proj-b", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, append `?cursor=<next_cursor>` to your request. You can also specify `limit` (default 20) as a query parameter.

**Example (List Tasks with Pagination):**

Before (v1):
```bash
curl -H "X-Auth-Token: <your_api_key>" \
  https://api.zrb.com/tasks
```

After (v2):
```bash
curl -H "Authorization: Bearer <your_api_token>" \
  https://api.zrb.com/v2/tasks?limit=10
```

```bash
# To fetch the next page
curl -H "Authorization: Bearer <your_api_token>" \
  https://api.zrb.com/v2/tasks?cursor=cursor_xyz&limit=10
```

## Migration Checklist

To migrate your application from Zrb CLI v1 to v2, follow these steps:

1.  [ ] **Update CLI:** Upgrade your Zrb CLI installation to v2.
2.  [ ] **Endpoint Paths:** Change all API endpoint paths from `/tasks` to `/v2/tasks` (and similarly for other resources if applicable).
3.  [ ] **Authentication:** Update your authentication header from `X-Auth-Token` to `Authorization: Bearer <your_api_token>`.
4.  [ ] **Task IDs:** Adjust your code to handle task `id`s as UUID strings instead of integers. This includes parsing, storage, and passing IDs in requests.
5.  [ ] **Task Completion Field:** Rename all references to the `done` field to `completed` in your task objects and API requests (e.g., when creating or updating tasks).
6.  [ ] **Project ID for Task Creation:** Ensure that all task creation requests include a `project_id` in the request body. If you don't have project concepts, consider a default project for all tasks initially.
7.  [ ] **List Endpoint Responses:** Update your code to parse list endpoint responses as a paginated envelope, accessing task items via the `items` array. Implement pagination logic using `cursor` and `limit` as needed.
8.  [ ] **Testing:** Thoroughly test your application with the new v2 API to ensure all functionalities work as expected.

## Upgrade Command

To upgrade your Zrb CLI, run the following command in your terminal:

```bash
# Please replace this with the actual upgrade command for Zrb CLI based on your installation method.
# For example, if installed via npm:
# npm install -g zrb-cli@latest
# If installed via pip:
# pip install --upgrade zrb-cli
# A common CLI upgrade command might be:
zrb upgrade
```
