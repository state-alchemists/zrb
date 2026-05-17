# Zrb API v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in Zrb API v2 and provides a step-by-step process for migrating your application.

## Summary of Breaking Changes

v2 introduces several key changes to improve security, scalability, and functionality:

1.  **API Version Prefix**: All endpoints are now prefixed with `/v2/`.
2.  **Authentication**: The authentication header has been updated to use a Bearer token.
3.  **Data Types**: The `id` field for tasks is now a UUID string instead of an integer.
4.  **Field Rename**: The `done` field in the Task object has been renamed to `completed`.
5.  **New Required Field**: Creating a task now requires a `project_id`.
6.  **Pagination**: List endpoints now return a structured, paginated response instead of a bare array.

---

## 1. API Version Prefix

All API endpoints are now prefixed with `/v2/` to version the API.

**v1:**
```
GET /tasks
POST /tasks
```

**v2:**
```
GET /v2/tasks
POST /v2/tasks
```

---

## 2. Authentication Header

Authentication now uses the standard `Authorization` header with a Bearer token, replacing the old `X-Auth-Token` header.

**v1:**
```
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.com/tasks
```

**v2:**
```
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.com/v2/tasks
```

---

## 3. Task ID Type (Integer to UUID)

The `id` field for tasks has been changed from an `integer` to a `UUID string`. This improves the uniqueness and scalability of task identifiers. Update any database columns or variables in your code that store task IDs.

**v1 Task Object:**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "..."
}
```

**v2 Task Object:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "..."
}
```

---

## 4. Field Rename (`done` to `completed`)

The boolean field indicating a task's status has been renamed from `done` to `completed` for clarity.

**v1 Update Request:**
```
PUT /tasks/42

{
  "done": true
}
```

**v2 Update Request:**
```
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890

{
  "completed": true
}
```

---

## 5. Required `project_id` on Creation

To support the new Projects feature, creating a task now requires a `project_id`. Tasks must be associated with a project.

**v1 Create Request:**
```
POST /tasks

{
  "title": "New task title"
}
```

**v2 Create Request:**
```
POST /v2/tasks

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

## 6. Paginated List Responses

The `GET /tasks` endpoint no longer returns a bare array of tasks. It now returns a paginated envelope containing the list of tasks in the `items` key. This improves performance for accounts with many tasks.

**v1 List Response:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**v2 List Response:**
```json
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v2", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
You must update your code to access the tasks via the `items` property of the response object. To fetch subsequent pages, use the `next_cursor` value.

---

## Migration Checklist

Follow these steps to migrate your application to v2:

- [ ] Update all API request paths to include the `/v2/` prefix.
- [ ] Change the authentication header from `X-Auth-Token` to `Authorization: Bearer <token>`.
- [ ] Update any code or database schemas that handle task `id`s to support UUID strings instead of integers.
- [ ] Rename all instances of the `done` field to `completed` in your code when reading or writing tasks.
- [ ] Add the required `project_id` field to all "create task" API calls.
- [ ] Update your logic for listing tasks to handle the new paginated response envelope (access tasks via the `items` key).

## Upgrade Command

To upgrade your Zrb CLI to the latest version, run:

```bash
zrb upgrade --to=v2
```
