# Migrating from Zrb Task API v1 to v2

Zrb Task API v2 introduces several breaking changes that affect authentication, endpoint paths, task payloads, and list response handling. If your integration already works against v1, you will need to update request headers, URL paths, request bodies, response parsing, and any code that assumes task IDs are integers.

This guide covers every breaking change between v1 and v2 and shows exactly what to change.

## At a Glance

The v2 breaking changes are:

1. All endpoints are now prefixed with `/v2/`
2. Authentication changed from `X-Auth-Token` to `Authorization: Bearer ...`
3. Task `id` changed from an integer to a UUID string
4. Task field `done` was renamed to `completed`
5. Creating a task now requires `project_id`
6. List endpoints now return a paginated envelope instead of a bare array

## 1. Update All Endpoint Paths

In v1, task endpoints lived under the root path. In v2, every endpoint is versioned under `/v2/`.

### What changed

- `GET /tasks` → `GET /v2/tasks`
- `GET /tasks/{id}` → `GET /v2/tasks/{id}`
- `POST /tasks` → `POST /v2/tasks`
- `PUT /tasks/{id}` → `PUT /v2/tasks/{id}`
- `DELETE /tasks/{id}` → `DELETE /v2/tasks/{id}`

### Before

```js
const response = await fetch('https://api.example.com/tasks');
const task = await fetch('https://api.example.com/tasks/42');
```

### After

```js
const response = await fetch('https://api.example.com/v2/tasks');
const task = await fetch('https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890');
```

## 2. Replace `X-Auth-Token` with Bearer Authentication

v1 accepted an API key in the `X-Auth-Token` header. v2 requires a Bearer token in the standard `Authorization` header.

Requests that continue sending `X-Auth-Token` will receive `401 Unauthorized`.

### Before

```bash
curl -H "X-Auth-Token: $ZRB_API_KEY" \
  https://api.example.com/tasks
```

```js
await fetch('https://api.example.com/tasks', {
  headers: {
    'X-Auth-Token': apiKey,
  },
});
```

### After

```bash
curl -H "Authorization: Bearer $ZRB_API_TOKEN" \
  https://api.example.com/v2/tasks
```

```js
await fetch('https://api.example.com/v2/tasks', {
  headers: {
    Authorization: `Bearer ${apiToken}`,
  },
});
```

## 3. Treat Task IDs as UUID Strings, Not Integers

In v1, task IDs were integers. In v2, task IDs are UUID strings.

This is a breaking change anywhere your code:

- stores IDs in integer-typed fields
- validates IDs as numeric
- parses IDs with `parseInt`, `Number`, or equivalent
- builds routes, cache keys, or database columns assuming numeric IDs

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
const response = await fetch(`https://api.example.com/tasks/${taskId}`);
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
const response = await fetch(`https://api.example.com/v2/tasks/${taskId}`);
```

### Migration notes

- Change application types from `number` or `integer` to `string`
- Remove numeric parsing of task IDs
- Review persistence layers and schemas that store task IDs
- Review tests that use numeric fixture IDs

## 4. Rename `done` to `completed`

The task status field was renamed in v2.

This affects:

- response parsing
- create/update payloads
- serializers and deserializers
- filters, UI bindings, and tests that read `done`

### Before

```json
{
  "title": "Updated title",
  "done": true
}
```

```js
const isDone = task.done;

await fetch(`https://api.example.com/tasks/${task.id}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'X-Auth-Token': apiKey,
  },
  body: JSON.stringify({ done: true }),
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
const isCompleted = task.completed;

await fetch(`https://api.example.com/v2/tasks/${task.id}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiToken}`,
  },
  body: JSON.stringify({ completed: true }),
});
```

### Migration notes

If you have a domain model named `done`, you can keep it internally during migration, but your API boundary must translate it to and from `completed`.

## 5. Include `project_id` When Creating Tasks

In v1, creating a task only required `title`. In v2, `project_id` is required for task creation.

If you omit `project_id`, the API returns `422 Unprocessable Entity`.

### Before

```bash
curl -X POST https://api.example.com/tasks \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  -d '{
    "title": "New task title"
  }'
```

```js
await fetch('https://api.example.com/tasks', {
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

### After

```bash
curl -X POST https://api.example.com/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  -d '{
    "title": "New task title",
    "project_id": "proj_abc123"
  }'
```

```js
await fetch('https://api.example.com/v2/tasks', {
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

### Migration notes

You will need a source of truth for `project_id` before creating tasks. In practice, that usually means one of the following:

- your application already knows the current project context
- you add project selection to your workflow
- you persist a default project ID in configuration

## 6. Update List Handling for Paginated Responses

In v1, `GET /tasks` returned a bare JSON array. In v2, `GET /v2/tasks` returns a pagination envelope with `items`, `total`, and `next_cursor`.

This is a breaking change for any code that expects the top-level response to be an array.

### Before

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```js
const response = await fetch('https://api.example.com/tasks', {
  headers: {
    'X-Auth-Token': apiKey,
  },
});

const tasks = await response.json();
for (const task of tasks) {
  console.log(task.title, task.done);
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
const response = await fetch('https://api.example.com/v2/tasks?limit=20', {
  headers: {
    Authorization: `Bearer ${apiToken}`,
  },
});

const page = await response.json();
for (const task of page.items) {
  console.log(task.title, task.completed);
}

if (page.next_cursor) {
  const nextPage = await fetch(
    `https://api.example.com/v2/tasks?cursor=${encodeURIComponent(page.next_cursor)}`,
    {
      headers: {
        Authorization: `Bearer ${apiToken}`,
      },
    }
  );
}
```

### Migration notes

- Read tasks from `response.items`, not the top-level JSON value
- Use `next_cursor` to continue pagination
- Do not assume a single request returns the full dataset
- If you previously used array operations directly on the response body, update that code first

## Endpoint-by-Endpoint Mapping

| v1 | v2 | Breaking change |
|---|---|---|
| `GET /tasks` | `GET /v2/tasks` | Path changed, response shape changed, pagination added |
| `GET /tasks/{id}` | `GET /v2/tasks/{id}` | Path changed, `id` is now a UUID string |
| `POST /tasks` | `POST /v2/tasks` | Path changed, auth changed, `project_id` required |
| `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` | Path changed, `id` is now a UUID string, `done` renamed to `completed` |
| `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` | Path changed, `id` is now a UUID string |

## Recommended Migration Strategy

For most codebases, the least risky order is:

1. update your base URL/path construction to include `/v2`
2. switch authentication to `Authorization: Bearer ...`
3. update your task model to use string IDs and `completed`
4. update task creation flows to require `project_id`
5. update list parsing to consume paginated envelopes
6. run integration tests against create, list, get, update, and delete flows

## Migration Checklist

- [ ] Change every task endpoint from `/tasks...` to `/v2/tasks...`
- [ ] Replace `X-Auth-Token` with `Authorization: Bearer <token>`
- [ ] Update token/config naming if your code distinguishes API keys from API tokens
- [ ] Change task ID types from integer/number to string
- [ ] Remove any numeric parsing or numeric validation for task IDs
- [ ] Update request and response models from `done` to `completed`
- [ ] Update all task update payloads to send `completed`
- [ ] Update response parsing, UI bindings, and tests to read `completed`
- [ ] Update create-task payloads to include `project_id`
- [ ] Decide where `project_id` comes from in your application flow
- [ ] Update list-task parsing to read from `items`
- [ ] Implement pagination handling using `next_cursor`
- [ ] Review tests and fixtures for numeric IDs, bare list arrays, and `done`
- [ ] Re-run end-to-end API tests against v2

Upgrade command:

```bash
zrb upgrade v2
```
