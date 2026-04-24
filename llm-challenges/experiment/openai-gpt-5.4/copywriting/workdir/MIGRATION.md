# Zrb CLI v1 → v2 Migration Guide

This guide is for developers already integrating with the Zrb Task API v1 and upgrading existing clients to v2.

## Overview

Zrb v2 introduces six breaking changes:

1. All endpoints are now prefixed with `/v2/`
2. Authentication changed from `X-Auth-Token` to `Authorization: Bearer ...`
3. Task `id` changed from an integer to a UUID string
4. Task field `done` was renamed to `completed`
5. Creating a task now requires `project_id`
6. List endpoints now return a paginated envelope instead of a bare array

If your codebase wraps API access cleanly, the simplest path is to update your HTTP client first, then migrate request/response models, then update list handling and task creation flows.

## Breaking Change 1: Endpoint paths are now versioned

In v1, task endpoints were rooted at `/tasks`. In v2, every endpoint is under `/v2/`.

### What changed

- `GET /tasks` → `GET /v2/tasks`
- `GET /tasks/{id}` → `GET /v2/tasks/{id}`
- `POST /tasks` → `POST /v2/tasks`
- `PUT /tasks/{id}` → `PUT /v2/tasks/{id}`
- `DELETE /tasks/{id}` → `DELETE /v2/tasks/{id}`

### Before

```js
const baseUrl = 'https://api.zrb.example';
const response = await fetch(`${baseUrl}/tasks`);
```

### After

```js
const baseUrl = 'https://api.zrb.example';
const response = await fetch(`${baseUrl}/v2/tasks`);
```

## Breaking Change 2: Authentication header changed

v1 accepted an API key in `X-Auth-Token`. v2 requires a Bearer token in the `Authorization` header.

Requests that still send `X-Auth-Token` will get `401 Unauthorized` in v2.

### Before

```bash
curl -H "X-Auth-Token: $ZRB_API_KEY" \
  https://api.zrb.example/tasks
```

### After

```bash
curl -H "Authorization: Bearer $ZRB_API_TOKEN" \
  https://api.zrb.example/v2/tasks
```

### Before

```js
await fetch(`${baseUrl}/tasks`, {
  headers: {
    'X-Auth-Token': apiKey,
  },
});
```

### After

```js
await fetch(`${baseUrl}/v2/tasks`, {
  headers: {
    Authorization: `Bearer ${apiToken}`,
  },
});
```

## Breaking Change 3: Task IDs are now UUID strings

In v1, `task.id` was an integer. In v2, `task.id` is a UUID string.

This affects:

- route parameters
- client-side type definitions
- database columns or cache keys if you stored task IDs as integers
- validation logic that assumes numeric IDs

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

### Before

```ts
type Task = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};

function getTask(id: number) {
  return fetch(`${baseUrl}/tasks/${id}`);
}
```

### After

```ts
type Task = {
  id: string;
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
};

function getTask(id: string) {
  return fetch(`${baseUrl}/v2/tasks/${id}`);
}
```

## Breaking Change 4: `done` was renamed to `completed`

The v1 task field `done` no longer exists in v2. Anywhere you read or write `done` must be updated to `completed`.

This applies to:

- response parsing
- update payloads
- UI state mapping
- filtering logic
- tests and fixtures

### Before

```js
if (task.done) {
  console.log('Task is finished');
}

await fetch(`${baseUrl}/tasks/${task.id}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ done: true }),
});
```

### After

```js
if (task.completed) {
  console.log('Task is finished');
}

await fetch(`${baseUrl}/v2/tasks/${task.id}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ completed: true }),
});
```

## Breaking Change 5: Task creation now requires `project_id`

In v1, creating a task only required `title`. In v2, `project_id` is mandatory.

If you omit `project_id`, the API returns `422`.

### Before

```bash
curl -X POST https://api.zrb.example/tasks \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title":"New task title"}'
```

### After

```bash
curl -X POST https://api.zrb.example/v2/tasks \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"New task title","project_id":"proj_abc123"}'
```

### Before

```js
await fetch(`${baseUrl}/tasks`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Auth-Token': apiKey,
  },
  body: JSON.stringify({ title: 'New task title' }),
});
```

### After

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

## Breaking Change 6: List responses are now paginated envelopes

In v1, `GET /tasks` returned a bare array. In v2, `GET /v2/tasks` returns an object with `items`, `total`, and `next_cursor`.

You must update any code that:

- assumes the top-level response is an array
- loops directly over the parsed JSON response
- ignores pagination
- expects all tasks in a single response

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

### Before

```js
const response = await fetch(`${baseUrl}/tasks`);
const tasks = await response.json();

for (const task of tasks) {
  console.log(task.title);
}
```

### After

```js
const response = await fetch(`${baseUrl}/v2/tasks?limit=20`, {
  headers: {
    Authorization: `Bearer ${apiToken}`,
  },
});

const page = await response.json();

for (const task of page.items) {
  console.log(task.title);
}

if (page.next_cursor) {
  console.log(`Fetch next page with ?cursor=${page.next_cursor}`);
}
```

## Full request mapping reference

| v1 | v2 |
|---|---|
| `GET /tasks` | `GET /v2/tasks` |
| `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| `POST /tasks` | `POST /v2/tasks` |
| `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |
| `X-Auth-Token: <key>` | `Authorization: Bearer <token>` |
| `id: integer` | `id: UUID string` |
| `done` | `completed` |
| create body: `{ "title": "..." }` | create body: `{ "title": "...", "project_id": "..." }` |
| list response: bare array | list response: `{ items, total, next_cursor }` |

## Recommended migration order

1. Update your base URL or route builder to prepend `/v2/`.
2. Replace `X-Auth-Token` with `Authorization: Bearer ...`.
3. Change task ID types from integers to strings everywhere in your codebase.
4. Rename all request/response field usage from `done` to `completed`.
5. Update task creation flows to always provide `project_id`.
6. Refactor list parsing to read `items` from the envelope.
7. Add pagination support using `next_cursor` and `limit` where needed.
8. Regenerate or update fixtures, mocks, and contract tests.

## Migration checklist

- [ ] Change all endpoint paths from `/tasks` to `/v2/tasks`
- [ ] Update authentication from `X-Auth-Token` to `Authorization: Bearer <token>`
- [ ] Replace any numeric task ID assumptions with UUID string handling
- [ ] Update task model definitions to use `completed` instead of `done`
- [ ] Add `project_id` to every task creation request
- [ ] Update create-task validation and tests to cover missing `project_id` as an error
- [ ] Refactor list-task consumers to read `response.items` instead of treating the response as an array
- [ ] Add pagination handling using `next_cursor`
- [ ] Update mocks, fixtures, serializers, and deserializers for the new v2 task shape
- [ ] Run your integration tests against all task endpoints in v2

`zrb upgrade v2`
