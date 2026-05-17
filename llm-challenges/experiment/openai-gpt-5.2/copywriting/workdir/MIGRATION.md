# Zrb Task API v1 → v2 Migration Guide

This guide covers all breaking changes between the v1 and v2 Zrb Task API, with before/after examples for each change.

## Overview of breaking changes (v1 → v2)

1. Base path changed: endpoints are now prefixed with `/v2/`
2. Authentication changed: `X-Auth-Token` header replaced by `Authorization: Bearer ...`
3. Task `id` changed type: integer → UUID string
4. Task status field renamed: `done` → `completed`
5. Task creation requires a project: `project_id` is now required
6. List endpoints are now paginated: bare array → envelope with `items`, `total`, `next_cursor`

---

## 1) Base path prefix: `/tasks` → `/v2/tasks`

In v2, all endpoints are namespaced under `/v2/`. Any request to the v1 paths will no longer hit the v2 API.

Before (v1):
```http
GET /tasks
```

After (v2):
```http
GET /v2/tasks
```

Apply this change consistently across all endpoints you call:

Before (v1):
```http
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

After (v2):
```http
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

## 2) Authentication header: `X-Auth-Token` → `Authorization: Bearer`

v2 switches from an API key header to a Bearer token header. Requests using `X-Auth-Token` will receive HTTP 401.

Before (v1):
```http
X-Auth-Token: <your_api_key>
```

After (v2):
```http
Authorization: Bearer <your_api_token>
```

Example request (curl)

Before (v1):
```bash
curl -sS https://api.example.com/tasks \
  -H 'X-Auth-Token: YOUR_KEY'
```

After (v2):
```bash
curl -sS https://api.example.com/v2/tasks \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

---

## 3) Task `id` type: integer → UUID string

In v1, task IDs are integers (e.g., `42`). In v2, IDs are UUID strings (e.g., `a1b2...`).

What breaks:
- URL construction and route matching if you validate IDs as integers
- Database schema / persistence layers that store task IDs as `int`
- Client-side types (e.g., TypeScript `number` → `string`)

Before (v1 task object):
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

After (v2 task object):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Example: URL building

Before (v1):
```js
const taskId = 42; // number
const url = `/tasks/${taskId}`;
```

After (v2):
```js
const taskId = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'; // string (UUID)
const url = `/v2/tasks/${taskId}`;
```

---

## 4) Field rename: `done` → `completed`

The task completion boolean is renamed in v2.

What breaks:
- JSON decoding/encoding
- Update payloads that still send `done`
- UI logic that reads `task.done`

Before (v1):
```json
{
  "title": "Updated title",
  "done": true
}
```

After (v2):
```json
{
  "title": "Updated title",
  "completed": true
}
```

Example: client-side mapping

Before (v1):
```ts
type TaskV1 = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};

function isComplete(task: TaskV1) {
  return task.done;
}
```

After (v2):
```ts
type TaskV2 = {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
};

function isComplete(task: TaskV2) {
  return task.completed;
}
```

---

## 5) Create Task requires `project_id`

In v2, every task belongs to a project. Creating a task now requires `project_id`. Omitting it returns HTTP 422.

Before (v1):
```http
POST /tasks
Content-Type: application/json

{"title":"New task title"}
```

After (v2):
```http
POST /v2/tasks
Content-Type: application/json

{"title":"New task title","project_id":"proj_abc123"}
```

Example (JavaScript)

Before (v1):
```js
await fetch('/tasks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'New task title' }),
});
```

After (v2):
```js
await fetch('/v2/tasks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123',
  }),
});
```

---

## 6) List responses are paginated: bare array → envelope

In v1, `GET /tasks` returns a JSON array. In v2, list endpoints return a paginated envelope with `items`, `total`, and `next_cursor`. Use `?cursor=<next_cursor>` to fetch subsequent pages.

Before (v1 response):
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

After (v2 response):
```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Buy milk",
      "completed": false,
      "project_id": "proj_abc123",
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Example: consuming list results

Before (v1):
```js
const res = await fetch('/tasks');
const tasks = await res.json(); // tasks is an array
for (const t of tasks) {
  console.log(t.title);
}
```

After (v2):
```js
const res = await fetch('/v2/tasks?limit=20');
const page = await res.json();

// page.items is the array
for (const t of page.items) {
  console.log(t.title);
}

// pagination
if (page.next_cursor) {
  const nextRes = await fetch(`/v2/tasks?cursor=${encodeURIComponent(page.next_cursor)}`);
  const nextPage = await nextRes.json();
  // ...
}
```

---

## Step-by-step migration checklist

1. Update all endpoint paths to include the `/v2/` prefix.
2. Replace `X-Auth-Token` with `Authorization: Bearer <token>` in every request.
3. Update your task ID handling:
   - Treat `id` as a string (UUID), not an integer.
   - Update any schema/types/validators and URL construction.
4. Rename task completion field usage:
   - Read `completed` instead of `done`.
   - Send `completed` instead of `done` in update payloads.
5. Update task creation flows to always include `project_id`.
   - Ensure your UI/config/service knows which project to create tasks under.
   - Handle HTTP 422 as a validation error if `project_id` is missing.
6. Update list consumers to handle pagination:
   - Expect an envelope `{ items, total, next_cursor }`.
   - Iterate over `items`.
   - Implement cursor pagination using `?cursor=<next_cursor>` (and optionally `limit`).
7. Run your integration tests against v2 and verify:
   - Authentication succeeds
   - CRUD operations work end-to-end
   - Pagination logic is correct for multi-page task lists

---

Upgrade command:

```bash
zrb upgrade v2
```
