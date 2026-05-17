# Zrb API v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in Zrb API v2 and provides a step-by-step process for migrating your application.

## Summary of Breaking Changes

Version 2 introduces several significant changes, including a new versioned API prefix, updated authentication, changes to the Task data model, and a new paginated response format for list endpoints.

---

## 1. API Endpoint Prefix

All API endpoints are now prefixed with `/v2/`.

### Before (v1)

```
GET /tasks
POST /tasks
```

### After (v2)

```
GET /v2/tasks
POST /v2/tasks
```

---

## 2. Authentication Header

Authentication now uses a Bearer token in the `Authorization` header, replacing the previous `X-Auth-Token`.

### Before (v1)

```
curl -X GET https://api.zrb.dev/tasks \
  -H "X-Auth-Token: <your_api_key>"
```

### After (v2)

```
curl -X GET https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer <your_api_token>"
```

---

## 3. Task ID Type Change

The `id` field for tasks has changed from an `integer` to a UUID `string`. Update any database columns or variables in your code that store task IDs to accommodate this new type.

### Before (v1)

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```
Example request: `GET /tasks/42`

### After (v2)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```
Example request: `GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890`

---

## 4. Field Rename: `done` to `completed`

The `done` boolean field on the Task object has been renamed to `completed`.

### Before (v1)

Updating a task:
```json
// PUT /tasks/42
{
  "title": "Updated title",
  "done": true
}
```

### After (v2)

Updating a task:
```json
// PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
{
  "title": "Updated title",
  "completed": true
}
```

---

## 5. Required `project_id` on Creation

Creating a new task now requires a `project_id`. Requests without this field will be rejected with an HTTP 422 error.

### Before (v1)

```json
// POST /tasks
{
  "title": "New task title"
}
```

### After (v2)

```json
// POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

## 6. Paginated List Responses

The `GET /tasks` endpoint no longer returns a bare array of tasks. It now returns a paginated envelope containing the list of tasks in the `items` field. Your code must be updated to handle this new structure and to use the `next_cursor` for pagination.

### Before (v1)

**Response from `GET /tasks`:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2)

**Response from `GET /v2/tasks`:**
```json
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
To fetch the next page, pass the cursor as a query parameter: `GET /v2/tasks?cursor=cursor_xyz`.

---

## Migration Checklist

Follow these steps to migrate your application to v2:

- [ ] **Update API Base URL:** Add the `/v2/` prefix to all API request paths.
- [ ] **Update Authentication:** Change the `X-Auth-Token` header to `Authorization: Bearer <token>`.
- [ ] **Update Task ID Type:** Change the data type for stored Task IDs from integer to string/UUID.
- [ ] **Update Task Model:** Rename the `done` field to `completed` in your code.
- [ ] **Update Create Task Calls:** Add the required `project_id` field to all `POST /v2/tasks` request bodies.
- [ ] **Update List Task Handling:** Modify code that calls `GET /v2/tasks` to parse the new paginated envelope and handle pagination using the `next_cursor`.

---

## Upgrade Command

To upgrade to the latest version of the Zrb CLI, run:

```bash
zrb upgrade --to=v2
```
