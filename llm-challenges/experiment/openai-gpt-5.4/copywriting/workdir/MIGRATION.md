# Migrating from Zrb CLI/API v1 to v2

This guide covers every breaking change between v1 and v2 of the Zrb Task API and shows exactly what to update in existing integrations. If your code already works against v1, the migration is straightforward, but you must update request URLs, authentication, task field names, ID handling, task creation payloads, and list response parsing.

## Overview of breaking changes

v2 introduces six breaking changes:

1. All endpoints are now prefixed with `/v2/`
2. Authentication changed from `X-Auth-Token` to `Authorization: Bearer ...`
3. Task `id` changed from integer to UUID string
4. Task field `done` was renamed to `completed`
5. Creating a task now requires `project_id`
6. List endpoints now return a paginated envelope instead of a bare array

## 1. Update all endpoint paths

In v1, task endpoints lived under the root path. In v2, every endpoint is namespaced under `/v2/`.

If you hardcoded endpoint paths anywhere in your client, tests, or SDK wrappers, update them all.

### Before

```http
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

### After

```http
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Example client change

Before:

```js
const baseUrl = 'https://api.example.com';
const response = await fetch(`${baseUrl}/tasks`);
```

After:

```js
const baseUrl = 'https://api.example.com';
const response = await fetch(`${baseUrl}/v2/tasks`);
```

## 2. Replace `X-Auth-Token` with Bearer authentication

v1 accepted an API key in the `X-Auth-Token` header. v2 requires a Bearer token in the standard `Authorization` header.

Requests that continue to send `X-Auth-Token` will fail with HTTP 401.

### Before

```http
X-Auth-Token: <your_api_key>
```

### After

```http
Authorization: Bearer <your_api_token>
```

### Example request change

Before:

```js
await fetch('https://api.example.com/tasks', {
  headers: {
    'X-Auth-Token': process.env.ZRB_API_KEY,
  },
});
```

After:

```js
await fetch('https://api.example.com/v2/tasks', {
  headers: {
    Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
  },
});
```

## 3. Treat task IDs as strings, not integers

In v1, task IDs were integers such as `42`. In v2, task IDs are UUID strings.

This is a breaking change anywhere you:
- parse IDs as numbers
- validate IDs as integers
- store IDs in numeric database columns
- build routes or cache keys assuming numeric IDs
- compare IDs with strict numeric logic

### Before

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
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

### Example type change

Before:

```ts
type Task = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};
```

After:

```ts
type Task = {
  id: string;
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
};
```

### Example usage change

Before:

```js
const taskId = Number(inputTaskId);
const response = await fetch(`${baseUrl}/tasks/${taskId}`);
```

After:

```js
const taskId = inputTaskId;
const response = await fetch(`${baseUrl}/v2/tasks/${taskId}`);
```

## 4. Rename `done` to `completed`

The task status field changed names in v2. Any code that reads or writes `done` must be updated to use `completed`.

This affects:
- response parsing
- request payloads
- UI bindings
- serialization and deserialization
- tests and fixtures

### Before

```json
{
  "title": "Updated title",
  "done": true
}
```

### After

```json
{
  "title": "Updated title",
  "completed": true
}
```

### Example response handling change

Before:

```js
if (task.done) {
  console.log('Task is complete');
}
```

After:

```js
if (task.completed) {
  console.log('Task is complete');
}
```

### Example update request change

Before:

```js
await fetch(`${baseUrl}/tasks/42`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'X-Auth-Token': apiKey,
  },
  body: JSON.stringify({ done: true }),
});
```

After:

```js
await fetch(`${baseUrl}/v2/tasks/${taskId}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiToken}`,
  },
  body: JSON.stringify({ completed: true }),
});
```

## 5. Include `project_id` when creating tasks

In v1, a task could be created with only a `title`. In v2, `project_id` is required on creation.

If you omit `project_id`, the server returns HTTP 422.

### Before

```json
{
  "title": "New task title"
}
```

### After

```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Example create request change

Before:

```js
await fetch(`${baseUrl}/tasks`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Auth-Token': apiKey,
  },
  body: JSON.stringify({
    title: 'New task title',
  }),
});
```

After:

```js
await fetch(`${baseUrl}/v2/tasks`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiToken}`,
  },
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123',
  }),
});
```

### Migration note

If your v1 integration had no concept of projects, you need to decide where `project_id` comes from before upgrading. In practice, most migrations either:
- map each existing workflow to a default project
- require callers to supply `project_id`
- look up the correct project before task creation

## 6. Update list handling for pagination

In v1, `GET /tasks` returned a bare array. In v2, `GET /v2/tasks` returns a paginated envelope with `items`, `total`, and `next_cursor`.

This is a breaking change if your code assumes the response body itself is an array.

### Before

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
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

### Example list parsing change

Before:

```js
const response = await fetch(`${baseUrl}/tasks`, {
  headers: { 'X-Auth-Token': apiKey },
});

const tasks = await response.json();
for (const task of tasks) {
  console.log(task.title, task.done);
}
```

After:

```js
const response = await fetch(`${baseUrl}/v2/tasks?limit=20`, {
  headers: { Authorization: `Bearer ${apiToken}` },
});

const page = await response.json();
for (const task of page.items) {
  console.log(task.title, task.completed);
}

if (page.next_cursor) {
  console.log('Fetch next page with cursor:', page.next_cursor);
}
```

### Example pagination loop

```js
let cursor = null;
const allTasks = [];

while (true) {
  const url = new URL(`${baseUrl}/v2/tasks`);
  url.searchParams.set('limit', '20');
  if (cursor) {
    url.searchParams.set('cursor', cursor);
  }

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${apiToken}`,
    },
  });

  const page = await response.json();
  allTasks.push(...page.items);

  if (!page.next_cursor) {
    break;
  }

  cursor = page.next_cursor;
}
```

## Endpoint-by-endpoint migration summary

### List tasks

Before:

```http
GET /tasks
X-Auth-Token: <your_api_key>
```

Returns:

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."}
]
```

After:

```http
GET /v2/tasks?limit=20
Authorization: Bearer <your_api_token>
```

Returns:

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

### Get task

Before:

```http
GET /tasks/42
X-Auth-Token: <your_api_key>
```

After:

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
```

### Create task

Before:

```http
POST /tasks
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "New task title"
}
```

After:

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

Before:

```http
PUT /tasks/42
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "Updated title",
  "done": true
}
```

After:

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

Before:

```http
DELETE /tasks/42
X-Auth-Token: <your_api_key>
```

After:

```http
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
```

## Step-by-step migration checklist

1. Update every API path from `/tasks...` to `/v2/tasks...`.
2. Replace `X-Auth-Token` with `Authorization: Bearer <token>` in every request.
3. Change task ID handling from integer to string UUID throughout your codebase, schemas, and storage.
4. Rename every reference to `done` to `completed` in request payloads, response handling, tests, and fixtures.
5. Add `project_id` to every task creation flow.
6. Update task model definitions to include `project_id` and the renamed `completed` field.
7. Change list response parsing to read from `response.items` instead of assuming the response is an array.
8. Implement cursor-based pagination where you need to fetch more than one page.
9. Update validation logic, serializers, mocks, and integration tests to match v2 response shapes.
10. Run your test suite against v2 endpoints and verify create, read, update, delete, and list flows.

Upgrade command:

```bash
zrb upgrade v2
```
