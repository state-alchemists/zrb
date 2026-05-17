# Zrb Task API v1 → v2 Migration Guide

This guide is for teams already using the Zrb Task API v1 and migrating clients, SDKs, and integrations to v2.

v2 introduces projects, cursor-based pagination, and stricter authentication. It also contains several breaking changes. This document walks through each one with concrete before/after examples and ends with a practical migration checklist.

---

## Overview of Breaking Changes

v2 makes the following breaking changes compared to v1:

1. All endpoints are now prefixed with `/v2/`.
2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer ...`.
3. Task `id` type changed from integer to UUID string.
4. Task field `done` renamed to `completed`.
5. Task creation now requires `project_id`.
6. List endpoints return a paginated envelope instead of a bare array.

Each section below details the impact and shows before/after code.

---

## 1. Endpoint prefix `/v2/`

### What changed

All task endpoints now live under the `/v2/` prefix. Existing `/tasks...` URLs will continue to exist only for v1; v2 clients must use `/v2/tasks...`.

### Impact

- Any hard-coded URLs must be updated.
- API clients/SDKs that generate URLs must include the `/v2/` prefix.

### Before (v1)

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
```

```http
GET /tasks/42 HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
```

### After (v2)

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
```

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
```

### Example client change (JavaScript)

```js
// v1
const BASE_URL = 'https://api.example.com';

async function listTasksV1(token) {
  const res = await fetch(`${BASE_URL}/tasks`, {
    headers: { 'X-Auth-Token': token },
  });
  return res.json(); // returns Task[]
}
```

```js
// v2
const BASE_URL = 'https://api.example.com';

async function listTasksV2(token) {
  const res = await fetch(`${BASE_URL}/v2/tasks`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await res.json();
  return body.items; // returns Task[] from envelope
}
```

---

## 2. Authentication header change

### What changed

v1 used a custom header. v2 uses a standard Bearer token scheme.

- v1: `X-Auth-Token: <your_api_key>`
- v2: `Authorization: Bearer <your_api_token>`

Requests using `X-Auth-Token` against v2 endpoints will receive HTTP 401.

### Impact

- HTTP clients, SDKs, and CLI tools must send the new header.
- Shared middleware (e.g., Axios interceptors, Fetch wrappers) must be updated.

### Before (v1)

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: my-v1-key
```

```js
// v1 Node.js fetch helper
function authHeadersV1(apiKey) {
  return { 'X-Auth-Token': apiKey };
}
```

### After (v2)

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer my-v2-token
```

```js
// v2 Node.js fetch helper
function authHeadersV2(apiToken) {
  return { Authorization: `Bearer ${apiToken}` };
}
```

---

## 3. Task `id` type: integer → UUID string

### What changed

The `id` field on tasks changed from an integer to a UUID string.

- v1 example:

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

- v2 example:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Impact

- Client models/types that assume `id: number` must be updated to `string`.
- URL builders and route parameters must treat `id` as a string.
- Databases that mirror the API may need schema migrations (e.g., integer → string/UUID column).

### Before (v1 TypeScript model)

```ts
// v1
export interface TaskV1 {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
}

async function getTaskV1(id: number): Promise<TaskV1> {
  const res = await fetch(`/tasks/${id}`);
  return res.json();
}
```

### After (v2 TypeScript model)

```ts
// v2
export interface TaskV2 {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
}

async function getTaskV2(id: string): Promise<TaskV2> {
  const res = await fetch(`/v2/tasks/${id}`);
  return res.json();
}
```

### Before (v1 URL usage)

```js
// id treated as number
const id = 42;
fetch(`/tasks/${id}`);
```

### After (v2 URL usage)

```js
// id is a UUID string
const id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
fetch(`/v2/tasks/${id}`);
```

---

## 4. Task field rename: `done` → `completed`

### What changed

The boolean field indicating task completion was renamed from `done` to `completed`.

- v1 field: `done: boolean`
- v2 field: `completed: boolean`

### Impact

- All serializers/deserializers must reference `completed` instead of `done`.
- Update requests must use `completed` in the JSON body.
- UI code bound to `task.done` must switch to `task.completed`.

### Before (v1 JSON payloads)

```json
// v1 task
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```http
PUT /tasks/42 HTTP/1.1
Content-Type: application/json

{
  "done": true
}
```

```js
// v1 UI binding
if (task.done) {
  renderCheckmark();
}
```

### After (v2 JSON payloads)

```json
// v2 task
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Content-Type: application/json

{
  "completed": true
}
```

```js
// v2 UI binding
if (task.completed) {
  renderCheckmark();
}
```

### Transitional adapter example

If you need to support both v1 and v2 payloads temporarily, introduce an adapter layer:

```ts
type TaskAny =
  | { id: number; title: string; done: boolean; created_at: string }
  | { id: string; title: string; completed: boolean; project_id: string; created_at: string };

interface NormalizedTask {
  id: string;
  title: string;
  completed: boolean;
  projectId?: string;
  createdAt: string;
}

function normalizeTask(task: TaskAny): NormalizedTask {
  return {
    id: String(task.id),
    title: task.title,
    completed: 'completed' in task ? task.completed : task.done,
    projectId: 'project_id' in task ? task.project_id : undefined,
    createdAt: task.created_at,
  };
}
```

---

## 5. Task creation requires `project_id`

### What changed

Creating a task now requires a `project_id` field. Omitting it results in HTTP 422.

- v1 allowed creating a task with just `title`.
- v2 requires both `title` and `project_id`.

### Impact

- Any code that creates tasks must supply a valid `project_id`.
- UI forms and CLI commands must collect or infer a `project_id`.

### Before (v1 Create Task)

```http
POST /tasks HTTP/1.1
Content-Type: application/json

{
  "title": "New task title"
}
```

```js
// v1 create call
async function createTaskV1(title) {
  const res = await fetch('/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  return res.json();
}
```

### After (v2 Create Task)

```http
POST /v2/tasks HTTP/1.1
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

```js
// v2 create call
async function createTaskV2(title, projectId) {
  const res = await fetch('/v2/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, project_id: projectId }),
  });

  if (!res.ok) {
    throw new Error(`Create failed: ${res.status}`);
  }

  return res.json();
}
```

---

## 6. List endpoints now return a paginated envelope

### What changed

`GET /tasks` no longer returns a bare JSON array. In v2, `GET /v2/tasks` returns a paginated envelope:

```json
{
  "items": [ /* Task objects */ ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Use `?cursor=<next_cursor>` to retrieve subsequent pages. If `next_cursor` is `null` or missing, there is no next page.

### Impact

- Client code must read tasks from `items` instead of treating the response as `Task[]`.
- List UIs can now show accurate totals and handle infinite scroll via `next_cursor`.

### Before (v1 List Tasks)

```http
GET /tasks HTTP/1.1

HTTP/1.1 200 OK
Content-Type: application/json

[
  { "id": 1, "title": "Buy milk", "done": false, "created_at": "..." },
  { "id": 2, "title": "Ship v1", "done": true, "created_at": "..." }
]
```

```js
// v1 client: assume response is Task[]
async function listTasksV1() {
  const res = await fetch('/tasks');
  const tasks = await res.json(); // tasks: Task[]
  return tasks;
}
```

### After (v2 List Tasks)

```http
GET /v2/tasks?limit=20 HTTP/1.1

HTTP/1.1 200 OK
Content-Type: application/json

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
      "id": "b2c3d4e5-f6a1-8907-abcd-ef1234567890",
      "title": "Ship v2",
      "completed": true,
      "project_id": "proj_xyz789",
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```js
// v2 client: handle envelope and pagination
async function listTasksV2(cursor) {
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);

  const res = await fetch(`/v2/tasks?${params.toString()}`);
  const { items, total, next_cursor } = await res.json();

  return { tasks: items, total, nextCursor: next_cursor };
}

async function listAllTasksV2() {
  let cursor = undefined;
  const all = [];

  do {
    const { tasks, nextCursor } = await listTasksV2(cursor);
    all.push(...tasks);
    cursor = nextCursor;
  } while (cursor);

  return all;
}
```

---

## Endpoint-by-endpoint comparison

### List Tasks

- v1: `GET /tasks` → `Task[]`
- v2: `GET /v2/tasks` → `{ items: TaskV2[], total: number, next_cursor: string | null }`

### Get Task

- v1: `GET /tasks/{id}` where `id` is an integer.
- v2: `GET /v2/tasks/{id}` where `id` is a UUID string.

### Create Task

- v1: `POST /tasks` with body `{ "title": string }`.
- v2: `POST /v2/tasks` with body `{ "title": string, "project_id": string }`.

### Update Task

- v1: `PUT /tasks/{id}` with body `{ "title"?: string, "done"?: boolean }`.
- v2: `PUT /v2/tasks/{id}` with body `{ "title"?: string, "completed"?: boolean }`.

### Delete Task

- v1: `DELETE /tasks/{id}`.
- v2: `DELETE /v2/tasks/{id}`.

---

## Migration Strategy

You can migrate incrementally by introducing v2-specific types and clients alongside v1, then switching call sites.

1. **Introduce v2 models and clients**
   - Add new `TaskV2` types with `id: string`, `completed: boolean`, and `project_id: string`.
   - Implement v2 client methods that target `/v2/...` endpoints and handle the new auth and pagination.

2. **Add an adapter layer (optional but recommended)**
   - Normalize both v1 and v2 responses to a common internal shape so your UI/business logic only changes once.

3. **Migrate authentication handling**
   - Update your HTTP client middleware/interceptors to send `Authorization: Bearer <token>` instead of `X-Auth-Token`.
   - Verify that all v2 calls include the correct header and that v1 calls continue to work during the transition if needed.

4. **Update ID handling**
   - Change any `number`-typed task IDs to `string`.
   - Review routing code, cache keys, and database schemas that assume numeric IDs.

5. **Rename `done` → `completed` in your codebase**
   - Update models, serializers, and UI bindings.
   - Ensure all update/create payloads use `completed`.

6. **Require and propagate `project_id`**
   - Decide how your app obtains `project_id` (user selection, default project, etc.).
   - Update all task-creation flows to set `project_id` and handle 422 errors for missing/invalid IDs.

7. **Adopt paginated list handling**
   - Refactor list views and batch processors to consume the envelope.
   - Implement cursor-based pagination where large result sets are expected.

8. **Switch traffic to v2**
   - Flip your feature flags or configuration to point all task traffic to v2.
   - Monitor logs for 4xx/5xx errors and adjust as needed.

---

## Step-by-step migration checklist

Use this checklist to track your migration.

1. [ ] Update all task endpoint URLs to use `/v2/...`.
2. [ ] Replace `X-Auth-Token` with `Authorization: Bearer <your_api_token>` everywhere.
3. [ ] Change task ID types from `number` to `string` in models, APIs, and database schemas.
4. [ ] Replace all usages of `done` with `completed` in:
   - [ ] Type/Model definitions
   - [ ] JSON serializers/deserializers
   - [ ] UI bindings and templates
   - [ ] Update payloads (`PUT /v2/tasks/{id}`)
5. [ ] Ensure all task creation calls send `project_id`:
   - [ ] Update request builders/clients
   - [ ] Update forms/CLI arguments
   - [ ] Handle HTTP 422 responses gracefully
6. [ ] Update list consumers to handle the paginated envelope:
   - [ ] Read tasks from `items`
   - [ ] Use `next_cursor` for subsequent pages
   - [ ] Use `total` for counts where needed
7. [ ] Add or update tests for:
   - [ ] Authentication header behavior
   - [ ] UUID `id` handling
   - [ ] `completed` field behavior
   - [ ] `project_id` requirements
   - [ ] Pagination logic
8. [ ] Remove deprecated v1-specific code paths once all consumers are on v2.

---

## Upgrade command

Run the following command to upgrade your Zrb CLI to v2:

```bash
zrb upgrade --major
```
