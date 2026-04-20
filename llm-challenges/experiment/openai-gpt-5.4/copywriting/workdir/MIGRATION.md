# Migrating from Zrb Task API v1 to v2

## Overview

Zrb Task API v2 introduces several breaking changes that require code updates in existing v1 clients. This guide focuses only on what experienced v1 users need to change to migrate safely.

## Breaking Changes at a Glance

v2 makes these breaking changes:

1. All endpoints are now prefixed with `/v2/`
2. Authentication changed from `X-Auth-Token` to `Authorization: Bearer ...`
3. Task `id` changed from an integer to a UUID string
4. Task field `done` was renamed to `completed`
5. Creating a task now requires `project_id`
6. List endpoints now return a paginated envelope instead of a bare array

## 1. Update Every Endpoint Path

In v1, task endpoints were mounted at the API root. In v2, every endpoint is versioned under `/v2/`.

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

### Migration notes

- Update any hardcoded paths in SDKs, API clients, tests, and mocks.
- Update route matching in integration tests and stub servers.
- `id` values shown in paths are now UUID strings, not integers.

## 2. Replace `X-Auth-Token` with Bearer Authentication

v1 accepted an API key in the `X-Auth-Token` header. v2 requires a Bearer token in the `Authorization` header. Requests using the old header will return `401`.

### Before
```http
X-Auth-Token: <your_api_key>
```

```javascript
fetch('/tasks', {
  headers: {
    'X-Auth-Token': apiKey
  }
})
```

### After
```http
Authorization: Bearer <your_api_token>
```

```javascript
fetch('/v2/tasks', {
  headers: {
    'Authorization': `Bearer ${apiToken}`
  }
})
```

### Migration notes

- Rename any config variable or secret wiring that assumes `X-Auth-Token` semantics.
- Update middleware, proxy rules, and test fixtures that inject auth headers.
- Verify all requests use the new header format, including background jobs and CLI wrappers.

## 3. Change Task `id` Handling from Integer to UUID String

In v1, task IDs were integers. In v2, task IDs are UUID strings.

This affects request paths, client-side types, database mappings, validation logic, and any code that assumes numeric comparison or parsing.

### Before
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
const taskId = 42
const url = `/tasks/${taskId}`
const isSameTask = task.id === 42
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

```javascript
const taskId = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
const url = `/v2/tasks/${taskId}`
const isSameTask = task.id === 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
```

### Migration notes

- Change task ID types from integer/number to string in your models and DTOs.
- Remove integer parsing such as `parseInt(task.id, 10)` or numeric validators.
- Review map keys, serializers, cache keys, and schema definitions that encode task IDs.

## 4. Rename `done` to `completed`

The task status field has been renamed. This applies both to task responses and update payloads.

### Before
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```json
{
  "title": "Updated title",
  "done": true
}
```

```javascript
if (task.done) {
  archive(task)
}

await fetch(`/tasks/${task.id}`, {
  method: 'PUT',
  body: JSON.stringify({ done: true })
})
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

```json
{
  "title": "Updated title",
  "completed": true
}
```

```javascript
if (task.completed) {
  archive(task)
}

await fetch(`/v2/tasks/${task.id}`, {
  method: 'PUT',
  body: JSON.stringify({ completed: true })
})
```

### Migration notes

- Rename every read, write, and assertion using `done`.
- Update API schemas, generated types, form bindings, and test fixtures.
- If you transform API payloads internally, make sure the mapping changes in both directions.

## 5. Include `project_id` When Creating Tasks

In v1, you could create a task with only a title. In v2, `project_id` is required when creating a task. Omitting it returns `422`.

### Before
```json
{
  "title": "New task title"
}
```

```javascript
await fetch('/tasks', {
  method: 'POST',
  body: JSON.stringify({
    title: 'New task title'
  })
})
```

### After
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

```javascript
await fetch('/v2/tasks', {
  method: 'POST',
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123'
  })
})
```

### Migration notes

- Update any create-task call sites to supply a project context.
- Add `project_id` to request validators, serializers, and test fixtures.
- If your v1 workflow had no project concept, determine where that value should come from before upgrading.

## 6. Update List Handling for Pagination

In v1, `GET /tasks` returned a bare array. In v2, `GET /v2/tasks` returns a paginated envelope with `items`, `total`, and `next_cursor`.

This is a breaking change for any code that deserializes the response directly into an array.

### Before
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
const response = await fetch('/tasks')
const tasks = await response.json()
for (const task of tasks) {
  console.log(task.title)
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

```javascript
const response = await fetch('/v2/tasks?limit=20')
const page = await response.json()
for (const task of page.items) {
  console.log(task.title)
}

if (page.next_cursor) {
  const nextResponse = await fetch(`/v2/tasks?cursor=${page.next_cursor}&limit=20`)
  const nextPage = await nextResponse.json()
}
```

### Migration notes

- Change response parsing from `Task[]` to a paginated envelope shape.
- Update list UIs and batch jobs to follow `next_cursor` when fetching multiple pages.
- If you previously relied on getting all tasks in one call, you now need pagination logic.
- `limit` is optional in v2 and defaults to `20`.

## Endpoint-by-Endpoint Migration Reference

### List Tasks

### Before
```http
GET /tasks
```

Response:
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."}
]
```

### After
```http
GET /v2/tasks?limit=20
Authorization: Bearer <your_api_token>
```

Response:
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

### Get Task

### Before
```http
GET /tasks/42
X-Auth-Token: <your_api_key>
```

### After
```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
```

### Create Task

### Before
```http
POST /tasks
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "New task title"
}
```

### After
```http
POST /v2/tasks
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Update Task

### Before
```http
PUT /tasks/42
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "Updated title",
  "done": true
}
```

### After
```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "Updated title",
  "completed": true
}
```

### Delete Task

### Before
```http
DELETE /tasks/42
X-Auth-Token: <your_api_key>
```

### After
```http
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <your_api_token>
```

## Recommended Migration Sequence

1. Switch your auth header from `X-Auth-Token` to `Authorization: Bearer ...`.
2. Change all endpoint paths to `/v2/...`.
3. Update task models:
   - `id: number` -> `id: string`
   - `done` -> `completed`
   - add `project_id`
4. Update create-task code to always send `project_id`.
5. Update update-task code to send `completed` instead of `done`.
6. Refactor list-task handling to parse `{ items, total, next_cursor }`.
7. Add or update pagination loops where you need all tasks, not just the first page.
8. Update test fixtures, mocks, contract tests, and generated client types.
9. Run integration tests against v2 endpoints and verify `401`/`422` handling for old request shapes is gone.

## Migration Checklist

- [ ] Replace every `/tasks` endpoint usage with `/v2/tasks`
- [ ] Replace `X-Auth-Token` with `Authorization: Bearer <token>`
- [ ] Change task ID types from integer/number to UUID string
- [ ] Stop treating task IDs as numeric values
- [ ] Rename every `done` field usage to `completed`
- [ ] Add `project_id` to task creation requests
- [ ] Update create-task validation to require `project_id`
- [ ] Update list response parsing from `Task[]` to `{ items, total, next_cursor }`
- [ ] Implement cursor-based pagination where full list traversal is required
- [ ] Update tests, fixtures, mocks, schemas, and generated clients for the new response and request shapes
- [ ] Verify create requests no longer fail with `422` due to missing `project_id`
- [ ] Verify requests no longer fail with `401` due to using `X-Auth-Token`

`zrb upgrade v2`
