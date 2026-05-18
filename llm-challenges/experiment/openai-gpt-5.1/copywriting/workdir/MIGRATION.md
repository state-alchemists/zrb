# Zrb Task API v1 → v2 Migration Guide

This guide explains how to move an existing Zrb Task API v1 integration to v2. It assumes you already use the v1 HTTP API and focuses only on breaking changes.

---

## 1. Overview of Breaking Changes

v2 introduces projects, cursor-based pagination, and stricter authentication. These changes are **not** backward compatible with v1.

Breaking changes you must handle:

1. All endpoints are now prefixed with `/v2/`
2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer`
3. Task `id` type changed from integer to UUID string
4. Task field `done` renamed to `completed`
5. Task creation now requires a `project_id`
6. List endpoints now return a paginated envelope instead of a bare array

Each section below explains the impact and shows before/after examples.

---

## 2. Endpoint Path Changes (`/tasks` → `/v2/tasks`)

### What changed

All task endpoints gained a `/v2` prefix. The underlying semantics are similar, but any hard-coded paths must be updated.

### Impact

- Any client using `/tasks`, `/tasks/{id}` must switch to `/v2/tasks`, `/v2/tasks/{id}`.
- Middleware, reverse proxies, or API gateway rules that match paths must be updated.

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

### Example: JavaScript client update

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
  return res.json(); // returns { items, total, next_cursor }
}
```

---

## 3. Authentication Header Change

### What changed

v1 used a custom header:

```http
X-Auth-Token: <your_api_key>
```

v2 uses a standard Bearer token:

```http
Authorization: Bearer <your_api_token>
```

Requests that still send `X-Auth-Token` will receive HTTP 401.

### Impact

- Any shared HTTP client, SDK, or middleware that injects `X-Auth-Token` must be updated.
- If you reuse the same token value, only the header name and format change; otherwise, ensure you provision a v2 token.

### Before (v1)

```bash
curl \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  https://api.example.com/tasks
```

### After (v2)

```bash
curl \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  https://api.example.com/v2/tasks
```

### Example: HTTP client wrapper

```python
# v1
import requests

BASE_URL = "https://api.example.com"

def get_task_v1(task_id: int, api_key: str):
    r = requests.get(
        f"{BASE_URL}/tasks/{task_id}",
        headers={"X-Auth-Token": api_key},
    )
    r.raise_for_status()
    return r.json()
```

```python
# v2
import requests

BASE_URL = "https://api.example.com"

def get_task_v2(task_id: str, api_token: str):
    r = requests.get(
        f"{BASE_URL}/v2/tasks/{task_id}",
        headers={"Authorization": f"Bearer {api_token}"},
    )
    r.raise_for_status()
    return r.json()
```

---

## 4. Task ID Type: Integer → UUID String

### What changed

The `id` field on `Task` is now a UUID string instead of an integer.

- v1: `"id": 42`
- v2: `"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"`

### Impact

- Database schemas or models that store task IDs as integers need to change to string/UUID.
- URL builders and route parameters must treat `id` as a string.
- Any ordering/offset logic based on integer IDs is no longer valid; use pagination cursors instead.

### Before (v1 Task model)

```ts
// v1 TypeScript type
export interface TaskV1 {
  id: number;
  title: string;
  done: boolean;
  created_at: string; // ISO timestamp
}
```

```ts
// Example usage
function getTaskUrlV1(id: number) {
  return `/tasks/${id}`;
}
```

### After (v2 Task model)

```ts
// v2 TypeScript type
export interface TaskV2 {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string; // ISO timestamp
}
```

```ts
// Example usage
function getTaskUrlV2(id: string) {
  return `/v2/tasks/${id}`;
}
```

### Example: Migration of storage schema

```sql
-- v1
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  done BOOLEAN NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
```

```sql
-- v2-compatible
CREATE TABLE tasks_v2 (
  id TEXT PRIMARY KEY,              -- store UUID as text
  title TEXT NOT NULL,
  completed BOOLEAN NOT NULL DEFAULT 0,
  project_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

---

## 5. Task Field Rename: `done` → `completed`

### What changed

The boolean field representing task completion is now called `completed` instead of `done`.

- v1 Task:
  - `done: false`
- v2 Task:
  - `completed: false`

### Impact

- Any deserialization, DTOs, or ORM mappings that reference `done` must be updated to `completed`.
- Update requests must send `completed` instead of `done`.

### Before (v1 JSON)

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```http
PUT /tasks/42
Content-Type: application/json

{
  "done": true
}
```

### After (v2 JSON)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json

{
  "completed": true
}
```

### Example: Client-side rename

```js
// v1
function isTaskDone(task) {
  return task.done;
}

function markDoneV1(id, token) {
  return fetch(`/tasks/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': token,
    },
    body: JSON.stringify({ done: true }),
  });
}
```

```js
// v2
function isTaskCompleted(task) {
  return task.completed;
}

function markCompletedV2(id, token) {
  return fetch(`/v2/tasks/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ completed: true }),
  });
}
```

---

## 6. New Required Field on Create: `project_id`

### What changed

Creating a task now requires a `project_id`.

- v1 `POST /tasks` accepted only `title`.
- v2 `POST /v2/tasks` requires both `title` and `project_id`; omitting `project_id` returns HTTP 422.

### Impact

- Any code that creates tasks must know which project they belong to.
- Background jobs or integrations that previously created tasks without project context must either:
  - Map to an existing project, or
  - Use a default project you create for that purpose.

### Before (v1 Create)

```http
POST /tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

Response:

```json
{
  "id": 42,
  "title": "New task title",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2 Create)

```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

Response:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "New task title",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Example: Updating a creator function

```ts
// v1
async function createTaskV1(title: string, token: string) {
  const res = await fetch('/tasks', {
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

```ts
// v2
async function createTaskV2(title: string, projectId: string, token: string) {
  const res = await fetch('/v2/tasks', {
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

## 7. List Response Shape: Bare Array → Paginated Envelope

### What changed

`GET /tasks` no longer returns a bare JSON array. All list endpoints now return a paginated envelope with `items`, `total`, and `next_cursor`.

- v1 response: `Task[]`
- v2 response: `{ items: TaskV2[], total: number, next_cursor: string | null }`

Use `?cursor=<next_cursor>` to fetch the next page.

### Impact

- Any code assuming `Array.isArray(response)` will break.
- You must access `response.items` to get the list of tasks.
- Infinite scroll / pagination components should be updated to use cursor-based pagination (`next_cursor`) instead of page numbers or offsets.

### Before (v1 List)

```http
GET /tasks
X-Auth-Token: <your_api_key>
```

Response:

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2 List)

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
      "project_id": "proj_default",
      "created_at": "..."
    },
    {
      "id": "b2c3d4e5-f6a1-8907-bcde-f12345678901",
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

### Example: Updating list consumption logic

```js
// v1: no pagination
async function fetchAllTasksV1(token) {
  const res = await fetch('/tasks', {
    headers: { 'X-Auth-Token': token },
  });
  const tasks = await res.json(); // tasks: TaskV1[]
  return tasks;
}
```

```js
// v2: cursor-based pagination
async function fetchAllTasksV2(token) {
  const all = [];
  let cursor = undefined;

  while (true) {
    const url = new URL('/v2/tasks', window.location.origin);
    if (cursor) url.searchParams.set('cursor', cursor);

    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${token}` },
    });

    const page = await res.json();
    all.push(...page.items);

    if (!page.next_cursor) break;
    cursor = page.next_cursor;
  }

  return all; // TaskV2[]
}
```

---

## 8. End-to-End Migration Example

This section shows a minimal end-to-end change set for a typical integration.

### Before: v1-only integration (TypeScript)

```ts
// models.ts
export interface Task {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
}

// api.ts
const BASE_URL = 'https://api.example.com';

export async function listTasks(apiKey: string): Promise<Task[]> {
  const res = await fetch(`${BASE_URL}/tasks`, {
    headers: { 'X-Auth-Token': apiKey },
  });
  return res.json();
}

export async function createTask(apiKey: string, title: string): Promise<Task> {
  const res = await fetch(`${BASE_URL}/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': apiKey,
    },
    body: JSON.stringify({ title }),
  });
  return res.json();
}

export async function markDone(apiKey: string, id: number): Promise<Task> {
  const res = await fetch(`${BASE_URL}/tasks/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': apiKey,
    },
    body: JSON.stringify({ done: true }),
  });
  return res.json();
}
```

### After: v2 integration (TypeScript)

```ts
// models.ts
export interface Task {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
}

export interface TaskListPage {
  items: Task[];
  total: number;
  next_cursor: string | null;
}

// api.ts
const BASE_URL = 'https://api.example.com';

export async function listTasks(token: string, cursor?: string): Promise<TaskListPage> {
  const url = new URL(`${BASE_URL}/v2/tasks`);
  if (cursor) url.searchParams.set('cursor', cursor);

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

export async function createTask(
  token: string,
  title: string,
  projectId: string,
): Promise<Task> {
  const res = await fetch(`${BASE_URL}/v2/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title, project_id: projectId }),
  });
  return res.json();
}

export async function markCompleted(token: string, id: string): Promise<Task> {
  const res = await fetch(`${BASE_URL}/v2/tasks/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ completed: true }),
  });
  return res.json();
}
```

---

## 9. Migration Checklist

Use this checklist to migrate an existing v1 integration to v2:

1. Endpoint paths
   - [ ] Replace all `/tasks` and `/tasks/{id}` paths with `/v2/tasks` and `/v2/tasks/{id}`.
   - [ ] Update API gateway / reverse-proxy routing rules to handle the `/v2` prefix.

2. Authentication
   - [ ] Remove usage of the `X-Auth-Token` header.
   - [ ] Add `Authorization: Bearer <your_api_token>` to all requests.
   - [ ] Ensure your deployment has a valid v2-compatible API token configured.

3. Task ID type
   - [ ] Change task ID types from integer to string/UUID in models, DTOs, and database schema.
   - [ ] Update any URL builders to accept string IDs.
   - [ ] Remove logic that depends on IDs being sequential integers.

4. `done` → `completed`
   - [ ] Rename the `done` field to `completed` in all Task models.
   - [ ] Update all update requests to send `{ "completed": true/false }` instead of `done`.
   - [ ] Update UI bindings or templates that read `task.done` to use `task.completed`.

5. `project_id` requirement
   - [ ] Decide how your integration chooses a `project_id` (per user, per workspace, or a default project).
   - [ ] Update all task creation calls to include `project_id`.
   - [ ] Adjust any tests/fixtures for task creation to provide a valid `project_id`.

6. List response pagination
   - [ ] Update list calls to consume `response.items` instead of assuming a bare array.
   - [ ] Implement cursor handling using `response.next_cursor` (loop until `null` if you need all items).
   - [ ] Update UI pagination / infinite scroll components to use cursor-based pagination.

7. Testing & rollout
   - [ ] Add unit tests or integration tests that target `/v2` endpoints.
   - [ ] Verify that all create, read, update, delete flows work end-to-end with v2.
   - [ ] Monitor logs for HTTP 401 and 422 responses after switching to v2.

---

## 10. Upgrade Command

Once your codebase is ready for the API changes above, upgrade your Zrb CLI to v2:

```bash
zrb upgrade --major
```
