# Zrb Task API v1 → v2 Migration Guide

This guide explains how to migrate existing Zrb Task API v1 integrations to v2. It assumes you already have code in production that talks to the v1 HTTP API.

v2 introduces projects, cursor-based pagination, and stricter authentication. It also contains several breaking changes that require code updates.

## Overview of Breaking Changes

v2 makes the following breaking changes relative to v1:

1. All endpoints are now prefixed with `/v2/`.
2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer ...`.
3. Task `id` type changed from integer to UUID string.
4. Task field `done` renamed to `completed`.
5. Task creation now requires a `project_id` field.
6. List endpoints return a paginated envelope instead of a bare array.

The sections below walk through each change with concrete before/after examples.

---

## 1. Endpoint paths now use the `/v2` prefix

All task endpoints that previously lived under `/tasks` are now under `/v2/tasks`.

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

### Example client change

JavaScript fetch example:

```js
// v1
const res = await fetch("https://api.example.com/tasks");

// v2
const res = await fetch("https://api.example.com/v2/tasks");
```

Make sure you update every hard-coded path, including in API clients, SDKs, documentation snippets, and tests.

---

## 2. Authentication header changed to Bearer tokens

v1 used a custom header `X-Auth-Token`. v2 uses the standard `Authorization: Bearer` header. Requests that still send `X-Auth-Token` will be rejected with HTTP 401.

### Before (v1)

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: your_api_key
```

JavaScript example:

```js
// v1
const res = await fetch("https://api.example.com/tasks", {
  headers: {
    "X-Auth-Token": process.env.ZRB_API_KEY,
  },
});
```

### After (v2)

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer your_api_token
```

JavaScript example:

```js
// v2
const res = await fetch("https://api.example.com/v2/tasks", {
  headers: {
    Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
  },
});
```

Update any HTTP clients, middleware, or SDK wrappers that set authentication headers.

---

## 3. Task `id` type changed from integer to UUID string

Task identifiers are now UUID strings instead of integers. This affects path parameters, types, database schemas, and any code that assumes numeric IDs.

### Before (v1)

Example task object:

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

Using the ID in an API call:

```http
GET /tasks/42
```

TypeScript model:

```ts
// v1
interface TaskV1 {
  id: number;
  title: string;
  done: boolean;
  created_at: string; // ISO 8601
}
```

### After (v2)

Example task object:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Using the ID in an API call:

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

TypeScript model:

```ts
// v2
interface TaskV2 {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string; // ISO 8601
}
```

If you persist task IDs locally (e.g., in a relational database), update the column type from integer to string/UUID and adjust validations accordingly.

---

## 4. Task status field renamed from `done` to `completed`

The boolean status field on tasks has been renamed.

### Before (v1)

Response shape:

```json
{
  "id": 42,
  "title": "Write tests",
  "done": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

Update request:

```http
PUT /tasks/42
Content-Type: application/json

{
  "done": true
}
```

Client code:

```ts
// v1
function markDone(task: TaskV1): Promise<TaskV1> {
  return http.put(`/tasks/${task.id}`, { done: true });
}
```

### After (v2)

Response shape:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Update request:

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json

{
  "completed": true
}
```

Client code:

```ts
// v2
function markCompleted(task: TaskV2): Promise<TaskV2> {
  return http.put(`/v2/tasks/${task.id}`, { completed: true });
}
```

Search your codebase for `done` usages related to tasks and migrate them to `completed`. Be careful not to rename unrelated variables that just happen to be called `done`.

---

## 5. Task creation now requires `project_id`

v2 introduces projects. Every task must belong to a project, referenced by `project_id`. This is a required field on task creation.

### Before (v1)

Create request:

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

Client code:

```ts
// v1
async function createTask(title: string) {
  const res = await http.post("/tasks", { title });
  return res.data; // TaskV1
}
```

### After (v2)

Create request (now requires `project_id`):

```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

If `project_id` is omitted, the API responds with HTTP 422 Unprocessable Entity.

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

Client code:

```ts
// v2
async function createTask(title: string, projectId: string) {
  const res = await http.post("/v2/tasks", {
    title,
    project_id: projectId,
  });
  return res.data; // TaskV2
}
```

You will need a strategy for how your application selects or stores `project_id` values (e.g., user chooses a project from a list, or you have a default project per workspace).

---

## 6. List endpoints now return a paginated envelope

In v1, list endpoints returned a bare JSON array of items. In v2, list endpoints return a paginated envelope with `items`, `total`, and `next_cursor`.

### Before (v1)

Request:

```http
GET /tasks
```

Response:

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

Client code:

```ts
// v1
async function listTasks(): Promise<TaskV1[]> {
  const res = await http.get("/tasks");
  return res.data; // TaskV1[]
}
```

### After (v2)

Request (with optional pagination params):

```http
GET /v2/tasks?limit=20
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
    },
    {
      "id": "b2c3d4e5-f6a1-8907-bcda-fe2345678901",
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

Client code:

```ts
// v2
interface PaginatedTasks {
  items: TaskV2[];
  total: number;
  next_cursor: string | null;
}

async function listTasks(cursor?: string): Promise<PaginatedTasks> {
  const res = await http.get("/v2/tasks", {
    params: {
      cursor,
      limit: 20,
    },
  });
  return res.data;
}

async function listAllTasks(): Promise<TaskV2[]> {
  const all: TaskV2[] = [];
  let cursor: string | undefined = undefined;

  while (true) {
    const page = await listTasks(cursor);
    all.push(...page.items);
    if (!page.next_cursor) break;
    cursor = page.next_cursor;
  }

  return all;
}
```

Update any code that assumed `GET /tasks` (or other list endpoints) returned a plain array. You now need to read from the `items` property and handle pagination if you need more than one page.

---

## Step-by-step migration checklist

Use this checklist to migrate an existing v1 client to v2 safely.

1. **Review dependencies and code ownership**
   - Identify all services, jobs, and libraries that call the Zrb Task API.
   - Ensure you can deploy and roll back each of them.

2. **Update endpoint paths**
   - Search for `/tasks` in your codebase.
   - Change all task-related paths to `/v2/tasks`.

3. **Switch authentication to Bearer tokens**
   - Replace uses of the `X-Auth-Token` header with `Authorization: Bearer <token>`.
   - Rotate or provision new v2-compatible tokens if required by your auth setup.

4. **Adjust ID types**
   - Change task ID types from integer to string/UUID in your models and database schema.
   - Remove any numeric operations on IDs (e.g., sorting numerically, range queries).

5. **Rename status field from `done` to `completed`**
   - Update all request payloads that send `done` to use `completed`.
   - Update all response models and UI components that read `done`.

6. **Require and propagate `project_id` on task creation**
   - Update task creation code to send `project_id`.
   - Decide how your application selects a `project_id` (UI, config, or defaults).
   - Add validations to ensure `project_id` is always present before calling the API.

7. **Handle paginated list responses**
   - Update list calls to read from `items` instead of assuming a bare array.
   - Implement cursor-based pagination if you need to load more than one page.
   - Update any tests or fixtures that assert on list response shapes.

8. **Run tests and validate end-to-end**
   - Add/adjust tests to cover the new response shapes and required fields.
   - Exercise common flows: list tasks, get task, create task, update task, delete task.

9. **Deploy and monitor**
   - Deploy the changes to a staging environment first.
   - Monitor logs for 4xx errors (401, 404, 422) related to the Zrb Task API.
   - Once stable, deploy to production and continue to monitor.

---

## Upgrade command

To upgrade the Zrb CLI to v2, run:

```bash
zrb upgrade --to 2
```
