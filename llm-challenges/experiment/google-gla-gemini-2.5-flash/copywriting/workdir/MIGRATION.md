# Zrb CLI v1 to v2 Migration Guide

This guide details the breaking changes and necessary steps to migrate your existing applications from Zrb CLI v1 to v2. Version 2 introduces significant improvements, including project support, enhanced pagination, and a more robust authentication mechanism.

## Major Changes Overview

The Zrb CLI v2 API has undergone several critical changes. Here’s a summary of what you need to be aware of:

*   **API Base Path**: All endpoints are now prefixed with `/v2/`.
*   **Authentication**: The authentication header has changed from `X-Auth-Token` to a standard `Authorization: Bearer` token.
*   **Task ID Type**: Task `id`s are now UUID strings instead of integers.
*   **Task Field Rename**: The `done` field on Task objects has been renamed to `completed`.
*   **New Required Field**: Creating a task now requires a `project_id`.
*   **Paginated Lists**: List endpoints now return a paginated envelope object instead of a bare array.

---

## Detailed Breaking Changes and Migration Steps

### 1. API Base Path

All API endpoints in v2 are now under the `/v2/` prefix.

**Before (v1):**
```
GET /tasks
POST /tasks
GET /tasks/{id}
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/{id}
```

**Migration:** Update all your API request URLs to include the `/v2/` prefix.

### 2. Authentication Header

The authentication method has been updated for better security and standardization.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

**Migration:** Change your HTTP client to send the `Authorization: Bearer` header with your API token instead of `X-Auth-Token`. Requests using the old header will result in an HTTP 401 Unauthorized error.

### 3. Task ID Type Change

The `id` field for Task objects has changed from an integer to a UUID string.

**Before (v1 Task Object):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2 Task Object):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Migration:** Update your code to expect and handle `id` as a string (UUID) instead of an integer when retrieving, updating, or deleting tasks.

### 4. Task Field `done` Renamed to `completed`

The boolean field indicating task completion has been renamed.

**Before (v1 Update Task Request Body):**
```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2 Update Task Request Body):**
```json
{
  "title": "Updated title",
  "completed": true
}
```

**Migration:** When creating or updating tasks, use `completed` instead of `done`. Similarly, when processing task objects received from the API, access the `completed` field.

### 5. Task Creation Requires `project_id`

A `project_id` is now a mandatory field when creating new tasks.

**Before (v1 Create Task Request Body):**
```json
{
  "title": "New task title"
}
```

**After (v2 Create Task Request Body):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Migration:** Ensure all task creation requests include a valid `project_id` in the request body. Omitting it will result in an HTTP 422 Unprocessable Entity error.

### 6. List Endpoints Return a Paginated Envelope

All list endpoints (e.g., `GET /v2/tasks`) now return a paginated response envelope, not a bare array.

**Before (v1 List Tasks Response):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2 List Tasks Response):**
```json
{
  "items": [
    {"id": "uuid1", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "uuid2", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```
**Pagination Query Parameters (v2):**
```
GET /v2/tasks?cursor=<next_cursor>&limit=20
```

**Migration:** Update your code to access the list of tasks from the `items` field within the response envelope. Implement logic to handle `total` and `next_cursor` for pagination, if desired.

---

## Migration Checklist

1.  [ ] Update all API endpoint URLs to include the `/v2/` prefix.
2.  [ ] Change authentication header from `X-Auth-Token` to `Authorization: Bearer <your_api_token>`.
3.  [ ] Adjust code to treat Task `id`s as UUID strings instead of integers.
4.  [ ] Replace all instances of the `done` field with `completed` in task request bodies and response parsing.
5.  [ ] Ensure all new task creation requests include a `project_id`.
6.  [ ] Modify code that consumes list endpoints to read tasks from the `items` array within the new paginated response envelope.
7.  [ ] (Optional) Implement pagination logic using `cursor` and `limit` query parameters for list endpoints.

---

## Upgrade Command

To upgrade your Zrb CLI installation to v2, run:

```bash
zrb upgrade --to v2
```
