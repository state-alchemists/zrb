# Migrating from Zrb CLI/API v1 to v2

Zrb v2 is not a drop-in upgrade for v1 clients. If your integration already works against v1, you will need to update request paths, authentication, task field names, ID handling, task creation payloads, and list response parsing.

This guide covers every documented breaking change between v1 and v2 and shows exactly what to change.

## At a Glance

The v2 breaking changes are:

1. All endpoints now use the `/v2/` prefix.
2. Authentication changed from `X-Auth-Token` to `Authorization: Bearer`.
3. Task `id` changed from an integer to a UUID string.
4. Task field `done` was renamed to `completed`.
5. Creating a task now requires `project_id`.
6. List endpoints now return a paginated envelope instead of a bare array.

## 1. Update All Endpoint Paths

Every v1 endpoint moved under the `/v2/` prefix. Any hard-coded v1 paths will break until they are updated.

### What changed

- v1: `/tasks`
- v2: `/v2/tasks`

This affects list, get, create, update, and delete operations.

### Before

```bash
curl https://api.example.com/tasks
curl https://api.example.com/tasks/42
curl -X POST https://api.example.com/tasks
curl -X PUT https://api.example.com/tasks/42
curl -X DELETE https://api.example.com/tasks/42
```

### After

```bash
curl https://api.example.com/v2/tasks
curl https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl -X POST https://api.example.com/v2/tasks
curl -X PUT https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl -X DELETE https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

## 2. Replace `X-Auth-Token` with Bearer Authentication

v2 no longer accepts the v1 authentication header. Requests using `X-Auth-Token` will return `401`.

### What changed

- v1 header: `X-Auth-Token: <your_api_key>`
- v2 header: `Authorization: Bearer <your_api_token>`

### Before

```bash
curl https://api.example.com/tasks \
  -H 'X-Auth-Token: my-api-key'
```

### After

```bash
curl https://api.example.com/v2/tasks \
  -H 'Authorization: Bearer my-api-token'
```

### Before

```javascript
const response = await fetch('https://api.example.com/tasks', {
  headers: {
    'X-Auth-Token': apiKey,
  },
});
```

### After

```javascript
const response = await fetch('https://api.example.com/v2/tasks', {
  headers: {
    Authorization: `Bearer ${apiToken}`,
  },
});
```

## 3. Treat Task IDs as UUID Strings, Not Integers

In v1, task IDs were integers. In v2, task IDs are UUID strings. Any code that parses IDs as numbers, stores them in integer columns, or validates them as numeric values must be updated.

### What changed

- v1 task ID: `42`
- v2 task ID: `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`

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

```javascript
const taskId = Number(inputTaskId);
const response = await fetch(`https://api.example.com/tasks/${taskId}`);
```

### After

```javascript
const taskId = inputTaskId;
const response = await fetch(`https://api.example.com/v2/tasks/${taskId}`);
```

### Migration notes

- Do not cast task IDs to numbers.
- Update schemas and types from integer to string.
- Update route validation and serializers to accept UUID-shaped strings.
- If you persist task IDs locally, verify the storage type can hold string UUIDs.

## 4. Rename `done` to `completed`

The task status field was renamed. Any code that reads or writes `done` must be changed to use `completed`.

### What changed

- v1 field: `done`
- v2 field: `completed`

This affects both response parsing and update payloads.

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

```javascript
if (task.done) {
  console.log('Task is finished');
}

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

```javascript
if (task.completed) {
  console.log('Task is finished');
}

await fetch(`https://api.example.com/v2/tasks/${task.id}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiToken}`,
  },
  body: JSON.stringify({ completed: true }),
});
```

## 5. Include `project_id` When Creating Tasks

Task creation is stricter in v2. A create request without `project_id` now fails with `422`.

### What changed

- v1 create payload required only `title`
- v2 create payload requires both `title` and `project_id`

### Before

```bash
curl -X POST https://api.example.com/tasks \
  -H 'X-Auth-Token: my-api-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "New task title"
  }'
```

### After

```bash
curl -X POST https://api.example.com/v2/tasks \
  -H 'Authorization: Bearer my-api-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "New task title",
    "project_id": "proj_abc123"
  }'
```

### Before

```javascript
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

```javascript
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

- Make sure your application has access to the correct `project_id` before creating tasks.
- Update any validation logic so `project_id` is required for create operations.
- If your UI or CLI previously created tasks without project context, you now need to collect or derive that value.

## 6. Parse List Responses as Paginated Envelopes

This is the biggest response-shape change in v2. List endpoints no longer return a bare array. They now return an envelope with `items`, `total`, and `next_cursor`.

### What changed

v1 list response:

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

v2 list response:

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

### Before

```javascript
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

```javascript
const response = await fetch('https://api.example.com/v2/tasks?limit=20', {
  headers: {
    Authorization: `Bearer ${apiToken}`,
  },
});

const page = await response.json();

for (const task of page.items) {
  console.log(task.title, task.completed);
}

console.log('Total tasks:', page.total);
console.log('Next cursor:', page.next_cursor);
```

### Before

```bash
curl https://api.example.com/tasks \
  -H 'X-Auth-Token: my-api-key'
```

### After

```bash
curl 'https://api.example.com/v2/tasks?limit=20&cursor=cursor_xyz' \
  -H 'Authorization: Bearer my-api-token'
```

### Migration notes

- Update any code that assumes the top-level response is an array.
- Iterate over `items`, not the root object.
- If you need complete result sets, follow `next_cursor` until it is empty or null.
- If you rely on total counts, use the new `total` field.

## Full Request Examples

### Get a Task

#### Before

```bash
curl https://api.example.com/tasks/42 \
  -H 'X-Auth-Token: my-api-key'
```

#### After

```bash
curl https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H 'Authorization: Bearer my-api-token'
```

### Update a Task

#### Before

```bash
curl -X PUT https://api.example.com/tasks/42 \
  -H 'X-Auth-Token: my-api-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Updated title",
    "done": true
  }'
```

#### After

```bash
curl -X PUT https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H 'Authorization: Bearer my-api-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Updated title",
    "completed": true
  }'
```

### Delete a Task

#### Before

```bash
curl -X DELETE https://api.example.com/tasks/42 \
  -H 'X-Auth-Token: my-api-key'
```

#### After

```bash
curl -X DELETE https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H 'Authorization: Bearer my-api-token'
```

## Migration Checklist

1. Change every request path from `/tasks` to `/v2/tasks`.
2. Replace the `X-Auth-Token` header with `Authorization: Bearer <token>`.
3. Update all task ID types from integer to string/UUID.
4. Remove numeric parsing or numeric validation for task IDs.
5. Rename all reads of `task.done` to `task.completed`.
6. Rename all writes of `done` in request payloads to `completed`.
7. Update task creation flows to always include `project_id`.
8. Add validation so create requests fail locally if `project_id` is missing.
9. Update list response parsing to read `items` instead of treating the response as an array.
10. If you fetch multiple pages, implement cursor handling with `next_cursor`.
11. If you depend on list counts, read `total` from the paginated response.
12. Run integration tests against all list, get, create, update, and delete paths before rolling out.

Upgrade command:

```bash
zrb upgrade v2
```
