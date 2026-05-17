# Zrb Task API v1 → v2 Migration Guide

v2 introduces projects, cursor-based pagination, and stricter authentication. This guide covers every breaking change and how to update your integration.

## Breaking Changes Overview

| Change | v1 | v2 |
|--------|----|----|
| API prefix | `/tasks` | `/v2/tasks` |
| Authentication header | `X-Auth-Token` | `Authorization: Bearer` |
| Task ID type | integer | UUID string |
| Task status field | `done` | `completed` |
| Required fields on create | `title` | `title`, `project_id` |
| List response format | bare array | paginated envelope |

---

## 1. Authentication Header

The authentication header has changed from a custom header to standard Bearer token authentication.

**Before (v1):**
```http
GET /tasks HTTP/1.1
X-Auth-Token: your_api_key
```

**After (v2):**
```http
GET /v2/tasks HTTP/1.1
Authorization: Bearer your_api_token
```

Requests using the old `X-Auth-Token` header will receive HTTP 401 Unauthorized.

---

## 2. Endpoint Prefix

All endpoints are now versioned under `/v2/`.

**Before (v1):**
```
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**
```
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 3. Task ID Type

Task IDs are now UUID strings instead of integers.

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

If you store task IDs in your database, update the column type from integer to string (VARCHAR/TEXT).

---

## 4. Task Status Field Rename

The `done` field has been renamed to `completed`.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": true
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true
}
```

Update any client code that reads or writes the `done` field:

**Before (v1):**
```javascript
if (task.done) {
  console.log("Task completed!");
}

// Updating task status
await fetch('/tasks/42', {
  method: 'PUT',
  body: JSON.stringify({ done: true })
});
```

**After (v2):**
```javascript
if (task.completed) {
  console.log("Task completed!");
}

// Updating task status
await fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  body: JSON.stringify({ completed: true })
});
```

---

## 5. Required `project_id` on Task Creation

Creating a task now requires a `project_id`. Tasks must belong to a project.

**Before (v1):**
```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

Omitting `project_id` returns HTTP 422 Unprocessable Entity. Retrieve available projects via `GET /v2/projects`.

---

## 6. Paginated List Response

List endpoints now return a paginated envelope instead of a bare array.

**Before (v1):**
```json
GET /tasks

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```json
GET /v2/tasks

{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc", "created_at": "..."},
    {"id": "b2c3...", "title": "Ship v2", "completed": true, "project_id": "proj_xyz", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Update your client code to:

1. Access tasks via `response.items` instead of treating the response as an array
2. Handle pagination using `next_cursor`

**Before (v1):**
```javascript
const tasks = await fetch('/tasks').then(r => r.json());
tasks.forEach(task => console.log(task.title));
```

**After (v2):**
```javascript
const response = await fetch('/v2/tasks').then(r => r.json());
response.items.forEach(task => console.log(task.title));

// Pagination
if (response.next_cursor) {
  const next = await fetch(`/v2/tasks?cursor=${response.next_cursor}`).then(r => r.json());
}
```

Pagination query parameters:
- `cursor` — pagination cursor from `next_cursor` (optional)
- `limit` — max results per page, default 20 (optional)

---

## Migration Checklist

- [ ] Update authentication header from `X-Auth-Token` to `Authorization: Bearer`
- [ ] Prefix all endpoints with `/v2/`
- [ ] Update task ID handling from integer to UUID string (database schemas, type definitions, URL builders)
- [ ] Rename all `done` field references to `completed` (read and write operations)
- [ ] Add `project_id` to all task creation requests
- [ ] Update list endpoint handlers to access `response.items` instead of treating response as array
- [ ] Implement pagination handling for list endpoints using `next_cursor`
- [ ] Run integration tests against v2 endpoints
- [ ] Update SDK/client library versions if applicable

---

## Upgrade Command

```bash
npm install zrb-client@^2.0.0
```

Or if using the CLI directly:

```bash
zrb upgrade --version 2
```