# Migrating from Zrb Task API v1 to v2

Zrb Task API v2 introduces several breaking changes that require updates in existing v1 clients. This guide is for developers who already use v1 and need a direct path to v2.

At a high level, you need to update request URLs, switch authentication headers, treat task IDs as strings instead of integers, rename the `done` field to `completed`, include `project_id` when creating tasks, and update list-handling code for paginated responses.

## Breaking changes at a glance

- All endpoints are now prefixed with `/v2/`
- Authentication changed from `X-Auth-Token` to `Authorization: Bearer ...`
- Task `id` changed from integer to UUID string
- Task field `done` was renamed to `completed`
- Creating a task now requires `project_id`
- List endpoints now return a pagination envelope instead of a bare array

## 1. Update all endpoint paths

In v1, task endpoints lived under the root path. In v2, every endpoint is namespaced under `/v2/`.

If your client hardcodes URLs, update every task endpoint.

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

### Example: base URL update

Before:

```js
const basePath = '/tasks';
const response = await fetch(basePath);
```

After:

```js
const basePath = '/v2/tasks';
const response = await fetch(basePath);
```

## 2. Change authentication from `X-Auth-Token` to Bearer auth

v1 accepted an API key in the `X-Auth-Token` header. v2 requires a Bearer token in the `Authorization` header.

Requests that still send `X-Auth-Token` will receive `401 Unauthorized` in v2.

### Before

```http
X-Auth-Token: <your_api_key>
```

### After

```http
Authorization: Bearer <your_api_token>
```

### Example: request headers

Before:

```js
await fetch('/tasks', {
  headers: {
    'X-Auth-Token': apiKey,
    'Content-Type': 'application/json'
  }
});
```

After:

```js
await fetch('/v2/tasks', {
  headers: {
    'Authorization': `Bearer ${apiToken}`,
    'Content-Type': 'application/json'
  }
});
```

## 3. Treat task IDs as UUID strings, not integers

In v1, task IDs were integers. In v2, task IDs are UUID strings.

This affects:
- Route construction
n- Client-side types and validation
- Database columns or caches that assume numeric IDs
- Sorting or comparisons that rely on numeric behavior

Do not parse task IDs as numbers in v2.

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

### Example: type update

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

### Example: path construction

Before:

```js
const taskId = 42;
await fetch(`/tasks/${taskId}`);
```

After:

```js
const taskId = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
await fetch(`/v2/tasks/${taskId}`);
```

## 4. Rename `done` to `completed`

The task status field was renamed from `done` to `completed` in v2.

This affects:
- Response parsing
- Request payloads for updates
- Client-side models and serializers
- Any filtering or rendering logic that references `done`

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

### Example: update payload

Before:

```json
{
  "title": "Updated title",
  "done": true
}
```

After:

```json
{
  "title": "Updated title",
  "completed": true
}
```

### Example: application code

Before:

```js
if (task.done) {
  renderCompleted(task);
}
```

After:

```js
if (task.completed) {
  renderCompleted(task);
}
```

## 5. Include `project_id` when creating tasks

In v1, creating a task only required `title`. In v2, `project_id` is required on task creation.

If you omit `project_id`, the API returns `422 Unprocessable Entity`.

### Before

```http
POST /tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

### After

```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Example: create request

Before:

```js
await fetch('/tasks', {
  method: 'POST',
  headers: {
    'X-Auth-Token': apiKey,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'New task title'
  })
});
```

After:

```js
await fetch('/v2/tasks', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${apiToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123'
  })
});
```

## 6. Update list handling for paginated responses

In v1, `GET /tasks` returned a bare array. In v2, `GET /v2/tasks` returns a pagination envelope with `items`, `total`, and `next_cursor`.

This is a breaking change for any code that assumes the response body is directly iterable.

### Before

```http
GET /tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After

```http
GET /v2/tasks?limit=20
```

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

### Example: list parsing

Before:

```js
const response = await fetch('/tasks');
const tasks = await response.json();

for (const task of tasks) {
  console.log(task.title);
}
```

After:

```js
const response = await fetch('/v2/tasks?limit=20');
const page = await response.json();

for (const task of page.items) {
  console.log(task.title);
}

if (page.next_cursor) {
  console.log('Fetch next page with cursor:', page.next_cursor);
}
```

### Example: cursor-based pagination

After:

```js
async function listAllTasks() {
  const allTasks = [];
  let cursor = null;

  do {
    const query = new URLSearchParams();
    query.set('limit', '20');
    if (cursor) query.set('cursor', cursor);

    const response = await fetch(`/v2/tasks?${query.toString()}`, {
      headers: {
        'Authorization': `Bearer ${apiToken}`
      }
    });

    const page = await response.json();
    allTasks.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);

  return allTasks;
}
```

## Full request examples

### Get a task

Before:

```bash
curl -H 'X-Auth-Token: YOUR_API_KEY' \
  https://api.example.com/tasks/42
```

After:

```bash
curl -H 'Authorization: Bearer YOUR_API_TOKEN' \
  https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Update a task

Before:

```bash
curl -X PUT \
  -H 'X-Auth-Token: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"done":true}' \
  https://api.example.com/tasks/42
```

After:

```bash
curl -X PUT \
  -H 'Authorization: Bearer YOUR_API_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"completed":true}' \
  https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

## Migration checklist

1. Update all task endpoint URLs to use the `/v2/` prefix.
2. Replace every `X-Auth-Token` header with `Authorization: Bearer <token>`.
3. Change task ID types in your client models from integer/number to string.
4. Remove any numeric parsing, validation, or sorting assumptions for task IDs.
5. Rename all references to `done` in request payloads, response parsing, and application logic to `completed`.
6. Add `project_id` to every task creation request.
7. Handle `422` responses for create requests that omit required fields.
8. Update task list parsing to read from `response.items` instead of assuming the response is an array.
9. Add support for `total` and `next_cursor` if your client lists more than one page of results.
10. Update integration tests and fixtures to use UUID task IDs, `completed`, and `project_id`.
11. Verify that get, create, update, list, and delete flows all work against `/v2/` endpoints.

Upgrade command:

```bash
zrb upgrade v2
```
