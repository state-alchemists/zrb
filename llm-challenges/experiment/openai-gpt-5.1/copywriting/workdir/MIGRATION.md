# Zrb Task API v1 → v2 Migration Guide

This guide walks through all breaking changes between the Zrb Task API v1 and v2, with concrete before/after examples so you can upgrade existing integrations safely.

---

## Overview of Breaking Changes

1. All endpoints are now prefixed with `/v2/`
2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer`
3. Task `id` type changed from integer to UUID string
4. Task field `done` renamed to `completed`
5. Task creation now requires `project_id`
6. List endpoints return a paginated envelope instead of a bare array

Each section below explains the impact and shows how to update existing code.

---

## 1. Endpoint Prefix: `/tasks` → `/v2/tasks`

All v2 endpoints are versioned under the `/v2` prefix. Unversioned endpoints (e.g. `/tasks`) will continue to behave as v1 or may be removed in a future major release.

### Before (v1)

```http
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

### After (v2)

```http
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Example: Updating a client wrapper

#### Before

```js
// apiClient-v1.js
const BASE_URL = 'https://api.example.com';

export async function getTask(id, token) {
  const res = await fetch(`${BASE_URL}/tasks/${id}`, {
    headers: { 'X-Auth-Token': token },
  });
  return res.json();
}
```

#### After

```js
// apiClient-v2.js
const BASE_URL = 'https://api.example.com/v2';

export async function getTask(id, token) {
  const res = await fetch(`${BASE_URL}/tasks/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}
```

---

## 2. Authentication Header Change

v1 used a custom header; v2 uses standard Bearer tokens.

- **v1:** `X-Auth-Token: <your_api_key>`
- **v2:** `Authorization: Bearer <your_api_token>`

Requests using the old header will receive **HTTP 401** in v2.

### Before (v1)

```http
GET /tasks
X-Auth-Token: my_v1_token
```

```bash
curl \
  -H "X-Auth-Token: my_v1_token" \
  https://api.example.com/tasks
```

### After (v2)

```http
GET /v2/tasks
Authorization: Bearer my_v2_token
```

```bash
curl \
  -H "Authorization: Bearer my_v2_token" \
  https://api.example.com/v2/tasks
```

### Example: Updating middleware

#### Before

```js
// express middleware (v1)
function attachAuth(req, res, next) {
  req.headers['X-Auth-Token'] = process.env.ZRB_API_TOKEN;
  next();
}
```

#### After

```js
// express middleware (v2)
function attachAuth(req, res, next) {
  req.headers.Authorization = `Bearer ${process.env.ZRB_API_TOKEN}`;
  next();
}
```

---

## 3. Task ID Type: Integer → UUID String

Task IDs are now globally unique string UUIDs instead of integers.

- **v1 example:** `42`
- **v2 example:** `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`

This affects:
- URL path parameters
- Local type definitions / schemas
- Database columns if you persist remote IDs

### Before (v1 Task Object)

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2 Task Object)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Example: Updating TypeScript types

#### Before

```ts
// types-v1.ts
export interface Task {
  id: number;
  title: string;
  done: boolean;
  created_at: string; // ISO 8601
}
```

#### After

```ts
// types-v2.ts
export interface Task {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string; // ISO 8601
}
```

### Example: Updating URL usage

#### Before

```js
const id = 42;
const res = await fetch(`https://api.example.com/tasks/${id}`, {
  headers: { 'X-Auth-Token': token },
});
```

#### After

```js
const id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
const res = await fetch(`https://api.example.com/v2/tasks/${id}`, {
  headers: { Authorization: `Bearer ${token}` },
});
```

---

## 4. `done` Field Renamed to `completed`

The task completion flag has been renamed.

- **v1 field:** `done: boolean`
- **v2 field:** `completed: boolean`

This impacts both read and write paths (responses and update payloads).

### Before (v1 read response)

```json
{
  "id": 1,
  "title": "Buy milk",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2 read response)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Buy milk",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Before (v1 update request)

```http
PUT /tasks/1
Content-Type: application/json
X-Auth-Token: my_v1_token

{
  "title": "Buy oat milk",
  "done": true
}
```

### After (v2 update request)

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json
Authorization: Bearer my_v2_token

{
  "title": "Buy oat milk",
  "completed": true
}
```

### Example: Updating mapping logic

#### Before

```js
function mapApiTaskToModel(apiTask) {
  return {
    id: apiTask.id,
    title: apiTask.title,
    isDone: apiTask.done,
    createdAt: new Date(apiTask.created_at),
  };
}
```

#### After

```js
function mapApiTaskToModel(apiTask) {
  return {
    id: apiTask.id,
    title: apiTask.title,
    isDone: apiTask.completed,
    projectId: apiTask.project_id,
    createdAt: new Date(apiTask.created_at),
  };
}
```

---

## 5. Task Creation Requires `project_id`

v2 introduces projects. Every task must belong to a project, and `project_id` is now **required** when creating tasks.

If you omit `project_id` in v2, the API returns **HTTP 422 Unprocessable Entity**.

### Before (v1 create request)

```http
POST /tasks
Content-Type: application/json
X-Auth-Token: my_v1_token

{
  "title": "New task title"
}
```

### After (v2 create request)

```http
POST /v2/tasks
Content-Type: application/json
Authorization: Bearer my_v2_token

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Example: Updating a create helper

#### Before

```js
export async function createTask(title, token) {
  const res = await fetch('https://api.example.com/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': token,
    },
    body: JSON.stringify({ title }),
  });
  return res.json();
}
```

#### After

```js
export async function createTask(title, projectId, token) {
  const res = await fetch('https://api.example.com/v2/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title, project_id: projectId }),
  });
  return res.json();
}
```

---

## 6. List Tasks Response: Bare Array → Paginated Envelope

List endpoints now return a paginated envelope instead of a bare array. This affects any code that:
- Assumes the response is an array
- Directly iterates over `response` instead of `response.items`

### Before (v1 list response)

```http
GET /tasks
X-Auth-Token: my_v1_token
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2 list response)

```http
GET /v2/tasks?limit=20
Authorization: Bearer my_v2_token
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
      "id": "b2c3d4e5-f6a1-8907-bcda-fe2345678901",
      "title": "Ship v2",
      "completed": true,
      "project_id": "proj_release",
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

### Example: Updating list consumption

#### Before

```js
// v1: response is an array
const res = await fetch('https://api.example.com/tasks', {
  headers: { 'X-Auth-Token': token },
});
const tasks = await res.json(); // tasks is Task[]

for (const task of tasks) {
  console.log(task.title);
}
```

#### After

```js
// v2: response is an envelope
const res = await fetch('https://api.example.com/v2/tasks?limit=20', {
  headers: { Authorization: `Bearer ${token}` },
});
const { items: tasks, total, next_cursor } = await res.json();

for (const task of tasks) {
  console.log(task.title);
}

if (next_cursor) {
  // fetch next page
  const nextRes = await fetch(
    `https://api.example.com/v2/tasks?cursor=${encodeURIComponent(next_cursor)}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  const nextPage = await nextRes.json();
  // handle nextPage.items, nextPage.next_cursor, etc.
}
```

### Example: Updating typed client

#### Before

```ts
// v1 client
const res = await fetch('/tasks', { headers: { 'X-Auth-Token': token } });
const tasks: Task[] = await res.json();
```

#### After

```ts
// v2 client
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  next_cursor: string | null;
}

const res = await fetch('/v2/tasks', {
  headers: { Authorization: `Bearer ${token}` },
});
const page: PaginatedResponse<Task> = await res.json();
const tasks = page.items;
```

---

## End-to-End Migration Example

This section shows a minimal end-to-end migration of a typical flow: list tasks, create a task, update it, and delete it.

### Before (v1)

```js
const BASE_URL = 'https://api.example.com';
const TOKEN = process.env.ZRB_API_TOKEN;

async function listTasks() {
  const res = await fetch(`${BASE_URL}/tasks`, {
    headers: { 'X-Auth-Token': TOKEN },
  });
  return res.json();
}

async function createTask(title) {
  const res = await fetch(`${BASE_URL}/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': TOKEN,
    },
    body: JSON.stringify({ title }),
  });
  return res.json();
}

async function completeTask(id) {
  const res = await fetch(`${BASE_URL}/tasks/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': TOKEN,
    },
    body: JSON.stringify({ done: true }),
  });
  return res.json();
}

async function deleteTask(id) {
  await fetch(`${BASE_URL}/tasks/${id}`, {
    method: 'DELETE',
    headers: { 'X-Auth-Token': TOKEN },
  });
}
```

### After (v2)

```js
const BASE_URL = 'https://api.example.com/v2';
const TOKEN = process.env.ZRB_API_TOKEN;

async function listTasks(limit = 20, cursor) {
  const url = new URL(`${BASE_URL}/tasks`);
  url.searchParams.set('limit', String(limit));
  if (cursor) url.searchParams.set('cursor', cursor);

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  return res.json(); // { items, total, next_cursor }
}

async function createTask(title, projectId) {
  const res = await fetch(`${BASE_URL}/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${TOKEN}`,
    },
    body: JSON.stringify({ title, project_id: projectId }),
  });
  return res.json();
}

async function completeTask(id) {
  const res = await fetch(`${BASE_URL}/tasks/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${TOKEN}`,
    },
    body: JSON.stringify({ completed: true }),
  });
  return res.json();
}

async function deleteTask(id) {
  await fetch(`${BASE_URL}/tasks/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
}
```

---

## Migration Checklist

Use this checklist to migrate an existing v1 integration to v2.

1. **Update base URLs and routes**
   - [ ] Change all `/tasks` endpoints to `/v2/tasks`.
   - [ ] Ensure any API client base URLs include `/v2`.

2. **Switch authentication header**
   - [ ] Replace all `X-Auth-Token` usages with `Authorization: Bearer <token>`.
   - [ ] Verify no legacy middleware still sets the old header.

3. **Update types and schemas**
   - [ ] Change task `id` from `number`/`integer` to `string` (UUID) in all models and database schemas.
   - [ ] Rename `done` field to `completed` everywhere (types, serialization, UI bindings, tests).
   - [ ] Add `project_id: string` to your task models.

4. **Refactor create flows**
   - [ ] Ensure every `POST /v2/tasks` call provides a valid `project_id`.
   - [ ] Update function signatures and forms to collect or derive `project_id`.

5. **Handle paginated list responses**
   - [ ] Update list consumers to read from `response.items` instead of assuming an array.
   - [ ] Introduce pagination handling using `limit` and `next_cursor` where appropriate.
   - [ ] Adjust tests and mocks to the new envelope shape (`{ items, total, next_cursor }`).

6. **End-to-end verification**
   - [ ] Run through core flows (list, create, update, delete) against a v2 environment.
   - [ ] Check logging/monitoring for HTTP 401 and 422 responses and fix remaining callers.
   - [ ] Remove any now-unused v1-specific code paths or feature flags.

---

## Upgrade Command

To install or upgrade to Zrb CLI v2, run:

```bash
npm install -g zrb@^2
```
