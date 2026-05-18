# Migrating from Zrb Task API v1 to v2

Zrb Task API v2 introduces several breaking changes that require updates in existing v1 clients. The biggest changes are the new `/v2/` route prefix, Bearer-token authentication, UUID task IDs, the `done` → `completed` field rename, required `project_id` on task creation, and paginated list responses.

This guide is for developers already using v1 and focuses only on what you must change to get a v1 integration working against v2.

## At a glance

These are all of the breaking changes between v1 and v2:

1. All endpoints are now prefixed with `/v2/`
2. Authentication changed from `X-Auth-Token` to `Authorization: Bearer ...`
3. Task `id` changed from integer to UUID string
4. Task field `done` was renamed to `completed`
5. Creating a task now requires `project_id`
6. List endpoints now return a paginated envelope instead of a bare array

## 1. Update all endpoint paths

In v1, task endpoints were mounted at `/tasks`. In v2, every endpoint is versioned under `/v2/`.

If you hardcoded URLs anywhere in your SDK, CLI wrapper, tests, or application code, update them all.

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

### Example

Before:

```js
const response = await fetch(`${baseUrl}/tasks`);
```

After:

```js
const response = await fetch(`${baseUrl}/v2/tasks`);
```

## 2. Replace `X-Auth-Token` with Bearer authentication

v1 accepted an API key in the `X-Auth-Token` header. v2 requires a Bearer token in the `Authorization` header.

Requests that continue sending `X-Auth-Token` will receive `401 Unauthorized`.

### Before

```http
X-Auth-Token: <your_api_key>
```

### After

```http
Authorization: Bearer <your_api_token>
```

### Example

Before:

```js
const response = await fetch(`${baseUrl}/tasks`, {
  headers: {
    'X-Auth-Token': apiKey,
  },
});
```

After:

```js
const response = await fetch(`${baseUrl}/v2/tasks`, {
  headers: {
    Authorization: `Bearer ${apiToken}`,
  },
});
```

## 3. Treat task IDs as strings, not integers

In v1, `task.id` was an integer. In v2, `task.id` is a UUID string.

This is a breaking change anywhere you:
- parse IDs as numbers
- validate IDs as integers
- use numeric database columns or schema types for cached task IDs
- build routes, maps, or typed models that assume `id: number`

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

### Example

Before:

```ts
type Task = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};

function getTaskUrl(id: number) {
  return `/tasks/${id}`;
}
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

function getTaskUrl(id: string) {
  return `/v2/tasks/${id}`;
}
```

## 4. Rename `done` to `completed`

The task status field has been renamed from `done` to `completed`.

This affects both response handling and update payloads. Any code still reading or writing `done` must be updated.

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

### Example: reading task state

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

### Example: updating task state

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
await fetch(`${baseUrl}/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiToken}`,
  },
  body: JSON.stringify({ completed: true }),
});
```

## 5. Include `project_id` when creating tasks

In v1, creating a task required only `title`. In v2, `project_id` is required for every task creation request.

If you omit `project_id`, the API returns `422 Unprocessable Entity`.

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

### Example

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

## 6. Update list handling for paginated responses

In v1, `GET /tasks` returned a bare array. In v2, list endpoints return an envelope with `items`, `total`, and `next_cursor`.

This is a breaking change for any code that assumes the response itself is an array.

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
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
      "title": "Ship v2",
      "completed": true,
      "project_id": "proj_abc123",
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

### Example: reading the list response

Before:

```js
const response = await fetch(`${baseUrl}/tasks`, {
  headers: {
    'X-Auth-Token': apiKey,
  },
});

const tasks = await response.json();
for (const task of tasks) {
  console.log(task.title);
}
```

After:

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
  console.log(`Fetch next page with cursor=${page.next_cursor}`);
}
```

### Example: following pagination

Before:

```js
const tasks = await fetch(`${baseUrl}/tasks`).then((r) => r.json());
```

After:

```js
let cursor;
const allTasks = [];

while (true) {
  const url = new URL(`${baseUrl}/v2/tasks`);
  if (cursor) url.searchParams.set('cursor', cursor);

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${apiToken}`,
    },
  });

  const page = await response.json();
  allTasks.push(...page.items);

  if (!page.next_cursor) break;
  cursor = page.next_cursor;
}
```

## Consolidated task model changes

If your codebase defines a shared task type, update it in one pass:

### Before

```ts
type Task = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};
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
```

## Migration checklist

1. Change every task API route from `/tasks` to `/v2/tasks`.
2. Replace `X-Auth-Token` with `Authorization: Bearer <token>` in every request.
3. Update all task ID handling from integer/number to UUID string.
4. Rename every `done` field reference to `completed`.
5. Add `project_id` to every task creation request.
6. Update task models, validators, serializers, and database/cache schemas to reflect:
   - `id: string`
   - `completed: boolean`
   - `project_id: string`
7. Change list-response parsing from a bare array to the paginated envelope:
   - read tasks from `items`
   - use `next_cursor` to fetch additional pages
   - optionally use `limit`
8. Update tests and fixtures to use `/v2/` paths, Bearer auth, UUID IDs, `completed`, and `project_id`.
9. Verify create flows fail fast if `project_id` is missing, since v2 returns HTTP 422.
10. Run an end-to-end smoke test for list, get, create, update, and delete against the v2 API.

Upgrade command:

```bash
zrb upgrade v2
```
