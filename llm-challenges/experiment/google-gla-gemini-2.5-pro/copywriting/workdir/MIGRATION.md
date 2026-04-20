# Zrb API v1 to v2 Migration Guide

Welcome to v2 of the Zrb Task API! This release introduces new features like projects and pagination, along with several important changes to improve consistency and security. This guide will walk you through all the breaking changes to ensure a smooth upgrade.

## Table of Contents
1.  [Breaking Change: API Path Versioning](#breaking-change-api-path-versioning)
2.  [Breaking Change: Authentication Method](#breaking-change-authentication-method)
3.  [Breaking Change: Paginated List Endpoints](#breaking-change-paginated-list-endpoints)
4.  [Breaking Change: Task Data Model](#breaking-change-task-data-model)
5.  [Breaking Change: Task Creation Requires Project ID](#breaking-change-task-creation-requires-project-id)
6.  [Migration Checklist](#migration-checklist)
7.  [Upgrading the CLI](#upgrading-the-cli)

---

### Breaking Change: API Path Versioning

All API endpoints are now prefixed with `/v2/` to ensure clear versioning.

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

---

### Breaking Change: Authentication Method

We have moved from a custom `X-Auth-Token` header to the industry-standard `Authorization` header with a Bearer token.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.com/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.com/v2/tasks
```
*Note: Requests using the old `X-Auth-Token` header will be rejected with a `401 Unauthorized` error.*

---

### Breaking Change: Paginated List Endpoints

The `GET /tasks` endpoint no longer returns a bare array of tasks. It now returns a paginated "envelope" object containing the list of items, the total count, and a cursor for fetching the next page.

**Before (v1):**
A `GET /tasks` request returned a simple JSON array.
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
A `GET /v2/tasks` request returns a structured object. You must now access the `items` property to get the tasks array.
```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, ...},
    {"id": "c3d4...", "title": "Ship v1", "completed": true, ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
To fetch the next page of results, pass the `next_cursor` value in the `cursor` query parameter: `GET /v2/tasks?cursor=cursor_xyz`.

---

### Breaking Change: Task Data Model

The `Task` object itself has two important changes: the `id` is now a string, and the `done` field has been renamed to `completed`.

#### 1. Task ID is now a UUID String

The `id` field for tasks has changed from an `integer` to a `UUID string`. You must update any variables or database columns that store task IDs to accommodate this new type.

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

#### 2. Field `done` renamed to `completed`

The boolean field indicating a task's status is now `completed`. This affects both reading and updating tasks.

**Before (v1):**
Updating a task:
```bash
curl -X PUT -d '{"done": true}' https://api.zrb.com/tasks/42
```
Task object payload:
```json
{
  "id": 42,
  "title": "...",
  "done": true
}
```

**After (v2):**
Updating a task:
```bash
curl -X PUT -d '{"completed": true}' https://api.zrb.com/v2/tasks/a1b2c3d4-...
```
Task object payload:
```json
{
  "id": "a1b2c3d4-...",
  "title": "...",
  "completed": true
}
```

---

### Breaking Change: Task Creation Requires Project ID

All tasks must now be associated with a project. The `project_id` field is now **required** when creating a new task.

**Before (v1):**
```bash
curl -X POST -d '{"title": "New task title"}' https://api.zrb.com/tasks
```

**After (v2):**
You must include a valid `project_id`.
```bash
curl -X POST -d '{"title": "New task title", "project_id": "proj_abc123"}' \
  https://api.zrb.com/v2/tasks
```
*Note: Requests without a `project_id` will be rejected with a `422 Unprocessable Entity` error.*

---

## Migration Checklist

Follow these steps to migrate your application from v1 to v2.

- [ ] **Update Base URL:** Prepend `/v2/` to all API endpoint paths.
- [ ] **Update Authentication:** Change the `X-Auth-Token` header to `Authorization: Bearer <token>`.
- [ ] **Update List Handling:** Modify code that calls `GET /tasks` to parse the new paginated response object (access the `items` array). Implement logic to handle pagination using the `next_cursor`.
- [ ] **Change ID Data Type:** Update any variables, function parameters, or database columns that handle the task `id` from `integer` to `string`.
- [ ] **Rename `done` Field:** In all API payloads and client-side logic, rename the `done` field to `completed`.
- [ ] **Add `project_id` to Creations:** Add the required `project_id` field to all `POST /v2/tasks` requests.

---

## Upgrading the CLI

To upgrade to the latest version, run:

```bash
zrb upgrade
```
