# Zrb API v1 to v2 Migration Guide

Welcome to v2 of the Zrb Task API! This release introduces new features like projects and improved pagination, along with several breaking changes. This guide provides a comprehensive overview to help you update your integration smoothly.

## Table of Contents
1. [API Endpoint Prefix](#1-api-endpoint-prefix)
2. [Authentication Header](#2-authentication-header)
3. [Task ID Type Change](#3-task-id-type-change-integer-to-uuid)
4. [Field Rename: `done` to `completed`](#4-field-rename-done-to-completed)
5. [Required `project_id` on Task Creation](#5-required-project_id-on-task-creation)
6. [Paginated List Responses](#6-paginated-list-responses)
7. [Migration Checklist](#migration-checklist)
8. [Upgrade Command](#upgrade-command)

---

### 1. API Endpoint Prefix

All API endpoints are now prefixed with `/v2/` to version the API.

**Before (v1):**
```
GET /tasks
POST /tasks
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
```

---

### 2. Authentication Header

Authentication now uses the industry-standard `Authorization: Bearer` token header instead of `X-Auth-Token`.

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

---

### 3. Task ID Type Change: Integer to UUID

The `id` field for Task objects has changed from an `integer` to a `UUID string`. This provides better uniqueness and scalability. You may need to update your database schema and any variables that store or handle task IDs.

**Before (v1):**
A Task `id` was an integer.
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```
Example request:
```
GET /tasks/42
```

**After (v2):**
The `id` is now a UUID string.
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123"
}
```
Example request:
```
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 4. Field Rename: `done` to `completed`

The boolean field indicating a task's status has been renamed from `done` to `completed` for clarity.

**Before (v1):**
```json
// Task Object
{
  "id": 1,
  "title": "Ship v1",
  "done": true
}

// Update Request
PUT /tasks/1
Content-Type: application/json

{
  "done": true
}
```

**After (v2):**
```json
// Task Object
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v1",
  "completed": true
}

// Update Request
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json

{
  "completed": true
}
```

---

### 5. Required `project_id` on Task Creation

With the introduction of Projects, creating a new task now requires a `project_id`. Requests without it will be rejected.

**Before (v1):**
A `title` was the only required field.
```http
POST /tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

**After (v2):**
`project_id` is now mandatory.
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

### 6. Paginated List Responses

Endpoints that return a list of objects (e.g., `GET /v2/tasks`) no longer return a bare array. Instead, they return a structured JSON envelope that includes pagination details.

**Before (v1):**
The response was a simple JSON array.
```json
[
  { "id": 1, "title": "Buy milk", "done": false },
  { "id": 2, "title": "Ship v1", "done": true }
]
```
Your code likely iterated directly over the response.
```javascript
const tasks = await response.json();
tasks.forEach(task => {
  console.log(task.title);
});
```

**After (v2):**
The response is an object containing the list in the `items` key, along with pagination info.
```json
{
  "items": [
    { "id": "...", "title": "Buy milk", "completed": false },
    { "id": "...", "title": "Ship v1", "completed": true }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
You must now access the `items` property to get the array. To fetch subsequent pages, pass the `next_cursor` value in the `cursor` query parameter.
```javascript
const responseBody = await response.json();
const tasks = responseBody.items;
tasks.forEach(task => {
  console.log(task.title);
});

if (responseBody.next_cursor) {
  // fetchNextPage(responseBody.next_cursor);
}
```

---

## Migration Checklist

Follow these steps to migrate your application from v1 to v2.

- [ ] **Update API Base URL:** Prepend `/v2/` to all API request paths.
- [ ] **Update Authentication:** Switch from `X-Auth-Token` header to `Authorization: Bearer <token>`.
- [ ] **Update ID Handling:** Change any variables, database columns, or logic that handle Task IDs from `integer` to `string` or `UUID`.
- [ ] **Rename `done` Field:** Search your codebase for the `done` property on Task objects and rename it to `completed`.
- [ ] **Add `project_id` to Creations:** Include the new required `project_id` field in all `POST /v2/tasks` requests.
- [ ] **Adapt to Paginated Responses:** Update any code that handles list responses to access the `.items` property and to handle pagination using the `next_cursor`.

---

## Upgrade Command

To upgrade to the latest version of the Zrb CLI, run:

```bash
zrb-cli upgrade --version=v2
```
