# Migrating from Zrb CLI v1 to v2

## Overview

Zrb CLI v2 introduces several breaking API changes. If your integration currently targets v1, you will need to update request URLs, authentication, task field names and types, task creation payloads, and list-response handling.

This guide covers every breaking change between v1 and v2, with before/after examples for each.

## Breaking Changes at a Glance

1. All endpoints are now prefixed with `/v2/`
2. Authentication changed from `X-Auth-Token` to `Authorization: Bearer ...`
3. Task `id` changed from an integer to a UUID string
4. Task field `done` was renamed to `completed`
5. Creating a task now requires `project_id`
6. List endpoints now return a paginated envelope instead of a bare array

## 1. Endpoint Prefix Changed

All v1 endpoints were unversioned. In v2, every endpoint is under `/v2/`.

### What changed

- `GET /tasks` → `GET /v2/tasks`
- `GET /tasks/{id}` → `GET /v2/tasks/{id}`
- `POST /tasks` → `POST /v2/tasks`
- `PUT /tasks/{id}` → `PUT /v2/tasks/{id}`
- `DELETE /tasks/{id}` → `DELETE /v2/tasks/{id}`

### Before

```bash
curl https://api.example.com/tasks/42
```

### After

```bash
curl https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

## 2. Authentication Header Changed

v1 used a custom header. v2 requires a Bearer token in the `Authorization` header.

Requests that still send `X-Auth-Token` will receive `401 Unauthorized`.

### Before

```bash
curl https://api.example.com/tasks \
  -H 'X-Auth-Token: your_api_key'
```

### After

```bash
curl https://api.example.com/v2/tasks \
  -H 'Authorization: Bearer your_api_token'
```

## 3. Task ID Type Changed: Integer → UUID String

In v1, task IDs were integers. In v2, task IDs are UUID strings.

This affects:

- URL path construction
- Type definitions and schema validation
- Database columns or cached payload assumptions
- Any code that sorts, compares, or parses IDs numerically

### Before

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```js
const taskId = 42;
const response = await client.get(`/tasks/${taskId}`);
```

### After

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

```js
const taskId = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
const response = await client.get(`/v2/tasks/${taskId}`);
```

## 4. Task Field Renamed: `done` → `completed`

The task completion field was renamed in v2.

This affects:

- Response parsing
- Request bodies for updates
- Serialization/deserialization logic
- Internal model mappings

### Before

```json
{
  "title": "Updated title",
  "done": true
}
```

```js
if (task.done) {
  archive(task);
}

await client.put(`/tasks/${task.id}`, {
  title: 'Updated title',
  done: true
});
```

### After

```json
{
  "title": "Updated title",
  "completed": true
}
```

```js
if (task.completed) {
  archive(task);
}

await client.put(`/v2/tasks/${task.id}`, {
  title: 'Updated title',
  completed: true
});
```

## 5. Creating a Task Now Requires `project_id`

In v1, you could create a task with only a title. In v2, `project_id` is required.

If you omit `project_id`, the API returns `422 Unprocessable Entity`.

### Before

```bash
curl https://api.example.com/tasks \
  -X POST \
  -H 'X-Auth-Token: your_api_key' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title"}'
```

### After

```bash
curl https://api.example.com/v2/tasks \
  -X POST \
  -H 'Authorization: Bearer your_api_token' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title","project_id":"proj_abc123"}'
```

### Before

```js
await client.post('/tasks', {
  title: 'New task title'
});
```

### After

```js
await client.post('/v2/tasks', {
  title: 'New task title',
  project_id: 'proj_abc123'
});
```

## 6. List Responses Changed: Bare Array → Paginated Envelope

In v1, list endpoints returned an array directly. In v2, list endpoints return an object containing `items`, `total`, and `next_cursor`.

This is the biggest response-shape change and will break any code that assumes `GET /tasks` returns an array.

### Before

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```js
const tasks = await client.get('/tasks');
for (const task of tasks) {
  console.log(task.title);
}
```

### After

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

```js
const page = await client.get('/v2/tasks');
for (const task of page.items) {
  console.log(task.title);
}

if (page.next_cursor) {
  const nextPage = await client.get(`/v2/tasks?cursor=${page.next_cursor}`);
}
```

### New list query parameters in v2

v2 list endpoints also support:

- `limit` — maximum results per page, default `20`
- `cursor` — fetch the next page returned by a previous response

Example:

```bash
curl 'https://api.example.com/v2/tasks?limit=50&cursor=cursor_xyz' \
  -H 'Authorization: Bearer your_api_token'
```

## Endpoint-by-Endpoint Migration Reference

### List tasks

#### v1

```http
GET /tasks
X-Auth-Token: <your_api_key>
```

#### v2

```http
GET /v2/tasks?limit=20&cursor=<optional>
Authorization: Bearer <your_api_token>
```

### Get task

#### v1

```http
GET /tasks/42
X-Auth-Token: <your_api_key>
```

#### v2

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
```

### Create task

#### v1

```http
POST /tasks
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "New task title"
}
```

#### v2

```http
POST /v2/tasks
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Update task

#### v1

```http
PUT /tasks/42
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "Updated title",
  "done": true
}
```

#### v2

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "Updated title",
  "completed": true
}
```

### Delete task

#### v1

```http
DELETE /tasks/42
X-Auth-Token: <your_api_key>
```

#### v2

```http
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
```

## Migration Checklist

1. Update every task API path to include the `/v2/` prefix.
2. Replace `X-Auth-Token` with `Authorization: Bearer <token>` in all requests.
3. Change task ID handling from integer to string UUID in your models, validation, and route construction.
4. Rename every usage of `done` to `completed` in both request payloads and response parsing.
5. Update task creation flows to always provide `project_id`.
6. Refactor all list-task consumers to read from `response.items` instead of treating the response as an array.
7. Add pagination handling using `next_cursor` where you need to fetch more than one page.
8. Update any tests, mocks, fixtures, and typed interfaces to match the v2 task schema and list envelope.
9. Verify create flows handle `422` when `project_id` is missing.
10. Verify old auth usage fails closed and that all migrated requests authenticate successfully.

`zrb upgrade v2`
