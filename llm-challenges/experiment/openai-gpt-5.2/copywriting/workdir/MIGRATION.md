# Zrb Task API v1 → v2 Migration Guide

This guide covers all breaking changes between the v1 and v2 Zrb Task API and shows exactly what to update in existing clients.

## Overview of breaking changes (v1 → v2)

1. Base path: all endpoints are now prefixed with `/v2/`
2. Authentication: `X-Auth-Token` header replaced with `Authorization: Bearer ...`
3. Task identifier: `id` changed from integer to UUID string
4. Task status field: `done` renamed to `completed`
5. Create task: `project_id` is now required
6. List responses: list endpoints return a paginated envelope (not a bare array)

---

## 1) Base path change: `/` → `/v2/`

Breaking change: every endpoint moved under the `/v2/` prefix.

Affected endpoints (examples):
- `GET /tasks` → `GET /v2/tasks`
- `GET /tasks/{id}` → `GET /v2/tasks/{id}`
- `POST /tasks` → `POST /v2/tasks`
- `PUT /tasks/{id}` → `PUT /v2/tasks/{id}`
- `DELETE /tasks/{id}` → `DELETE /v2/tasks/{id}`

Before (v1):
```bash
curl -sS \
  -H 'X-Auth-Token: YOUR_KEY' \
  https://api.example.com/tasks
```

After (v2):
```bash
curl -sS \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  https://api.example.com/v2/tasks
```

---

## 2) Authentication header change

Breaking change: API key header `X-Auth-Token` is no longer accepted.

v2 requires:

```
Authorization: Bearer <your_api_token>
```

Using `X-Auth-Token` will return HTTP 401.

Before (v1):
```bash
curl -sS \
  -H 'X-Auth-Token: YOUR_KEY' \
  https://api.example.com/tasks
```

After (v2):
```bash
curl -sS \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  https://api.example.com/v2/tasks
```

---

## 3) Task `id` type change: integer → UUID string

Breaking change: task IDs are no longer integers.

Before (v1 Task object):
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

After (v2 Task object):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Before (v1, using numeric `id` in path):
```bash
curl -sS \
  -H 'X-Auth-Token: YOUR_KEY' \
  https://api.example.com/tasks/42
```

After (v2, using UUID `id` in path):
```bash
curl -sS \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Migration notes:
- Update types in your client models (`int`/`number` → `string`).
- If you store task IDs (DB, cache, serialized payloads), adjust schema and any validation.

---

## 4) Field rename: `done` → `completed`

Breaking change: the task completion field was renamed.

This impacts:
- Reading task objects (`task.done` no longer exists)
- Update payloads (`done` is ignored/invalid; use `completed`)

Before (v1 update payload):
```json
{
  "title": "Updated title",
  "done": true
}
```

After (v2 update payload):
```json
{
  "title": "Updated title",
  "completed": true
}
```

Before (v1, list response item):
```json
{"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
```

After (v2, list response item):
```json
{
  "id": "...",
  "title": "Ship v1",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "..."
}
```

Migration notes:
- Rename fields in your DTOs/ORM structs.
- Update any logic that filters/counts “done” tasks.

---

## 5) Create task now requires `project_id`

Breaking change: `POST /v2/tasks` requires a `project_id`. Omitting it returns HTTP 422.

Before (v1 create payload):
```json
{
  "title": "New task title"
}
```

After (v2 create payload):
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

Before (v1):
```bash
curl -sS -X POST \
  -H 'X-Auth-Token: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title"}' \
  https://api.example.com/tasks
```

After (v2):
```bash
curl -sS -X POST \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title","project_id":"proj_abc123"}' \
  https://api.example.com/v2/tasks
```

Migration notes:
- Decide how your app chooses a `project_id` (config default, user selection, mapping from existing grouping, etc.).
- Update tests/fixtures to include `project_id`.

---

## 6) List endpoints now return a paginated envelope

Breaking change: `GET /v2/tasks` no longer returns a bare JSON array. It returns an object with pagination metadata.

Before (v1 list response):
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

After (v2 list response):
```json
{
  "items": [
    {
      "id": "...",
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

Pagination request pattern:
- First page: `GET /v2/tasks?limit=20`
- Next page: `GET /v2/tasks?cursor=<next_cursor>&limit=20`

Before (v1):
```js
// v1: tasks is an array
const tasks = await client.get('/tasks');
for (const t of tasks) {
  if (!t.done) console.log(t.title);
}
```

After (v2):
```js
// v2: response is an envelope
const page = await client.get('/v2/tasks?limit=20');
for (const t of page.items) {
  if (!t.completed) console.log(t.title);
}

// fetch next page if present
if (page.next_cursor) {
  const nextPage = await client.get(`/v2/tasks?cursor=${encodeURIComponent(page.next_cursor)}&limit=20`);
  // ...
}
```

Migration notes:
- Update deserialization: list responses are now objects, not arrays.
- If your UI previously assumed “all tasks” were returned, you must iterate pages until `next_cursor` is null/absent.

---

## Step-by-step migration checklist

1. Update your base URL construction to include `/v2/` for all task API calls.
2. Replace `X-Auth-Token` with `Authorization: Bearer <token>` everywhere.
3. Change task ID types in your client code and storage from integer/number to string (UUID).
4. Rename all uses of `done` to `completed`:
   - response parsing
   - update requests
   - business logic (filters, counts, UI labels)
5. Update task creation flows to supply a valid `project_id`.
6. Update list-task handling to parse the paginated envelope:
   - read from `items`
   - honor `limit`
   - follow `next_cursor` until exhausted (when you need a full list)
7. Update mocks/fixtures and tests to match v2 payloads and responses.
8. Run your integration test suite against v2 endpoints and verify:
   - auth failures return 401 when expected
   - create without `project_id` returns 422 (and your app never triggers it)
   - list pagination works end-to-end

Upgrade command:

```bash
zrb upgrade --major v2
```
