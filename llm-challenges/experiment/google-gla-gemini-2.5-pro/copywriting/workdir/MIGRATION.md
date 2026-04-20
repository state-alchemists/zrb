# Zrb API v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in Zrb API v2 and provides a step-by-step process for migrating your application.

## Table of Contents
- [Breaking Changes](#breaking-changes)
  - [1. API Endpoint Prefix](#1-api-endpoint-prefix)
  - [2. Authentication Header](#2-authentication-header)
  - [3. Task ID Format](#3-task-id-format)
  - [4. Field Rename: `done` is now `completed`](#4-field-rename-done-is-now-completed)
  - [5. Paginated List Responses](#5-paginated-list-responses)
  - [6. Mandatory `project_id` on Task Creation](#6-mandatory-project_id-on-task-creation)
- [Migration Checklist](#migration-checklist)
- [Upgrading](#upgrading)

---

## Breaking Changes

### 1. API Endpoint Prefix

All API endpoints are now prefixed with `/v2` to version the API.

**Before (v1):**
```
GET /tasks
POST /tasks
PUT /tasks/123
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 2. Authentication Header

Authentication now uses the `Authorization` header with a Bearer token, replacing the old `X-Auth-Token` header.

**Before (v1):**
```http
GET /tasks
X-Auth-Token: your_api_key
```

**After (v2):**
```http
GET /v2/tasks
Authorization: Bearer your_api_token
```

### 3. Task ID Format

The `id` field for tasks has changed from an `integer` to a `UUID string`. Any code that validates or stores task IDs must be updated to handle UUIDs.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "..."
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "..."
}
```

### 4. Field Rename: `done` is now `completed`

The boolean field indicating a task's status has been renamed from `done` to `completed` for clarity.

**Before (v1):**
```json
// Task object
{
  "id": 42,
  "title": "Ship v1",
  "done": true, 
  "created_at": "..."
}

// PUT /tasks/42
{
  "done": true
}
```

**After (v2):**
```json
// Task object
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v2",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "..."
}

// PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
{
  "completed": true
}
```

### 5. Paginated List Responses

The `GET /tasks` endpoint no longer returns a bare array. It now returns a paginated envelope object. You must update your code to access the tasks via the `items` key and handle pagination using the `next_cursor`.

**Before (v1):**
```
GET /tasks
```
Response:
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```
GET /v2/tasks
```
Response:
```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, ...},
    {"id": "b2c3...", "title": "Ship v2", "completed": true, ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
To fetch the next page, use the cursor:
```
GET /v2/tasks?cursor=cursor_xyz
```

### 6. Mandatory `project_id` on Task Creation

Creating a task now requires a `project_id`. This is a new required field that links each task to a project.

**Before (v1):**
```
POST /tasks
```
Request Body:
```json
{
  "title": "New task title"
}
```

**After (v2):**
```
POST /v2/tasks
```
Request Body:
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

## Migration Checklist

Follow these steps to migrate your integration:

- [ ] **Update API Base URL:** Change all API calls from `/<endpoint>` to `/v2/<endpoint>`.
- [ ] **Update Authentication:** Replace the `X-Auth-Token` header with the `Authorization: Bearer <token>` header.
- [ ] **Update ID Handling:** Change any variable types, database columns, or validation for Task IDs from `integer` to `string`/`UUID`.
- [ ] **Rename `done` field:** In your code, rename all instances of the `done` field in Task objects to `completed`.
- [ ] **Update List Task Handling:** Modify code that calls `GET /tasks` to parse the new paginated response envelope and handle pagination using the `cursor` parameter.
- [ ] **Add `project_id` to Create Task Calls:** Add the required `project_id` field to the body of all `POST /tasks` requests.

---

## Upgrading

To upgrade to the latest version of the Zrb CLI, run:

```bash
pip install --upgrade zrb
```
