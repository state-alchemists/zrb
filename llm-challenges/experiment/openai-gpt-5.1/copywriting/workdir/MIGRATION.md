# Zrb Task API v1 → v2 Migration Guide

This guide is for teams already integrated with the Zrb Task API v1 and upgrading to v2.

## Overview of Breaking Changes

v2 is not wire‑compatible with v1. Every client that talks to the Task API must be updated.

Breaking changes:

1. All endpoints are now prefixed with `/v2/`
2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer …`
3. Task `id` type changed from integer to UUID string
4. Task field `done` renamed to `completed`
5. Task creation now **requires** `project_id`
6. List endpoints return a paginated envelope instead of a bare array

The sections below walk through each change with before/after examples.

---

## 1. Endpoint paths now use `/v2/` prefix

**What changed**

All endpoints moved from unversioned paths to explicit versioned paths. Requests to the old paths will not see v2 behavior.

- v1: `GET /tasks`, `GET /tasks/{id}`, `POST /tasks`, ...
- v2: `GET /v2/tasks`, `GET /v2/tasks/{id}`, `POST /v2/tasks`, ...

**Before (v1)**

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
```

**After (v2)**

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
```

**Action required**

Update every hard‑coded path from `/tasks` to `/v2/tasks` (and analogous changes for other task endpoints).

---

## 2. Authentication header changed

**What changed**

Auth has moved from a custom header to standard Bearer tokens.

- v1 header: `X-Auth-Token: <your_api_key>`
- v2 header: `Authorization: Bearer <your_api_token>`

Requests using `X-Auth-Token` receive HTTP 401 under v2.

**Before (v1)**

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: 12345
```

**After (v2)**

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer 12345
```

**Example: JavaScript/TypeScript client**

Before:

```ts
// v1
const res = await fetch("https://api.example.com/tasks", {
  headers: {
    "X-Auth-Token": process.env.ZRB_API_KEY!,
  },
});
```

After:

```ts
// v2
const res = await fetch("https://api.example.com/v2/tasks", {
  headers: {
    Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
  },
});
```

**Action required**

- Replace all uses of `X-Auth-Token` with `Authorization: Bearer …`.
- Ensure your token provisioning/rotation process issues the correct v2 token.

---

## 3. Task `id` type changed: integer → UUID string

**What changed**

Task identifiers are now UUID strings instead of integers.

- v1: `"id": 42`
- v2: `"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"`

Any client code that assumes numeric IDs (e.g., integer parsing, database schema, URL builders) must be updated.

**Before (v1) response**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2) response**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Example: Type handling in a strongly typed client**

Before (TypeScript type):

```ts
// v1
type Task = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};
```

After (v2):

```ts
// v2
type Task = {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
};
```

**Example: URL building**

Before:

```ts
// v1
function getTaskUrl(id: number) {
  return `/tasks/${id}`;
}
```

After:

```ts
// v2
function getTaskUrl(id: string) {
  return `/v2/tasks/${id}`;
}
```

**Action required**

- Change task ID types from integer to string in your models and database schemas where applicable.
- Remove any numeric parsing or validation that rejects non‑numeric IDs.

---

## 4. Task `done` field renamed to `completed`

**What changed**

The boolean status field on tasks has been renamed.

- v1: `done` (default `false`)
- v2: `completed` (default `false`)

**Before (v1 task object)**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2 task object)**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Before (v1 Update Task request)**

```http
PUT /tasks/42 HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "Updated title",
  "done": true
}
```

**After (v2 Update Task request)**

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "Updated title",
  "completed": true
}
```

**Example: client mapping**

Before:

```ts
// v1
function isTaskDone(task: Task): boolean {
  return task.done;
}
```

After:

```ts
// v2
function isTaskCompleted(task: Task): boolean {
  return task.completed;
}
```

**Action required**

- Rename `done` → `completed` across your models, serializers/deserializers, and UI bindings.
- Update any filters/queries that refer to `done`.

---

## 5. Task creation now requires `project_id`

**What changed**

Tasks must now belong to a project. `project_id` is a required field on creation.

- v1 create body: `{ "title": "New task title" }`
- v2 create body: `{ "title": "New task title", "project_id": "proj_abc123" }`

Omitting `project_id` in v2 returns HTTP 422.

**Before (v1 Create Task)**

```http
POST /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "New task title"
}
```

**After (v2 Create Task)**

```http
POST /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Example: client helper**

Before:

```ts
// v1
async function createTask(title: string) {
  const res = await fetch("https://api.example.com/tasks", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Auth-Token": process.env.ZRB_API_KEY!,
    },
    body: JSON.stringify({ title }),
  });
  return res.json();
}
```

After:

```ts
// v2
async function createTask(title: string, projectId: string) {
  const res = await fetch("https://api.example.com/v2/tasks", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
    },
    body: JSON.stringify({ title, project_id: projectId }),
  });
  return res.json();
}
```

**Action required**

- Decide how your system maps or creates `project_id` values.
- Update any task‑creation flows to require and provide `project_id`.

---

## 6. List endpoints now return a paginated envelope

**What changed**

List endpoints no longer return a bare JSON array. Instead, they return an envelope with `items`, `total`, and `next_cursor`.

- v1 list response: `[{...}, {...}]`
- v2 list response: `{ "items": [{...}, {...}], "total": 42, "next_cursor": "cursor_xyz" }`

**Before (v1 List Tasks response)**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2 List Tasks response)**

```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Buy milk",
      "completed": false,
      "project_id": "proj_home",
      "created_at": "..."
    },
    {
      "id": "f0e9d8c7-b6a5-4321-bcde-fedcba987654",
      "title": "Ship v2",
      "completed": true,
      "project_id": "proj_release",
      "created_at": "..."
    }
  ],
  "total": 2,
  "next_cursor": null
}
```

**Example: client consuming list response**

Before:

```ts
// v1
const res = await fetch("https://api.example.com/tasks", {
  headers: { "X-Auth-Token": process.env.ZRB_API_KEY! },
});
const tasks: Task[] = await res.json();
console.log(tasks.length);
```

After:

```ts
// v2
const res = await fetch("https://api.example.com/v2/tasks?limit=20", {
  headers: { Authorization: `Bearer ${process.env.ZRB_API_TOKEN}` },
});
const page: { items: Task[]; total: number; next_cursor: string | null } = await res.json();

console.log(page.items.length);

if (page.next_cursor) {
  const nextRes = await fetch(
    `https://api.example.com/v2/tasks?cursor=${encodeURIComponent(page.next_cursor)}`,
    { headers: { Authorization: `Bearer ${process.env.ZRB_API_TOKEN}` } },
  );
  const nextPage = await nextRes.json();
}
```

**Action required**

- Update deserialization logic to read `items` instead of a top‑level array.
- Implement cursor‑based pagination using `next_cursor` where you previously relied on fetching all results.

---

## End-to-end example: full v1 vs v2 flow

### v1: create, list, update, delete

```http
# Create
POST /tasks
X-Auth-Token: <key>
Content-Type: application/json

{"title": "Write tests"}

# List
GET /tasks
X-Auth-Token: <key>

# Update
PUT /tasks/42
X-Auth-Token: <key>
Content-Type: application/json

{"done": true}

# Delete
DELETE /tasks/42
X-Auth-Token: <key>
```

### v2: create, list (paginated), update, delete

```http
# Create (requires project_id)
POST /v2/tasks
Authorization: Bearer <token>
Content-Type: application/json

{"title": "Write tests", "project_id": "proj_abc123"}

# List (paginated)
GET /v2/tasks?limit=20
Authorization: Bearer <token>

# Update (uses UUID id and completed)
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <token>
Content-Type: application/json

{"completed": true}

# Delete
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Authorization: Bearer <token>
```

---

## Migration Checklist

Use this checklist to plan and verify your upgrade.

1. **Inventory callers**
   - [ ] Locate all services, CLIs, and jobs that call the Zrb Task API.
   - [ ] Identify client libraries/SDKs that wrap the Task API.
2. **Update endpoint paths**
   - [ ] Replace all `/tasks` paths with `/v2/tasks` (and adjust any other task endpoints accordingly).
3. **Update authentication**
   - [ ] Switch from `X-Auth-Token` to `Authorization: Bearer <your_api_token>`.
   - [ ] Rotate or provision v2‑compatible tokens if needed.
4. **Adjust data models**
   - [ ] Change task `id` fields from integer to string/UUID.
   - [ ] Rename `done` → `completed` everywhere (models, DTOs, UI, tests).
   - [ ] Add required `project_id` to task models.
5. **Update request payloads**
   - [ ] Include `project_id` in all task creation requests.
   - [ ] Use `completed` (not `done`) in all update requests.
6. **Update response handling**
   - [ ] Expect paginated envelopes for list endpoints: `{ items, total, next_cursor }`.
   - [ ] Update any code assuming a top‑level JSON array of tasks.
7. **Implement pagination where needed**
   - [ ] Use `limit` and `cursor` query parameters when listing tasks.
   - [ ] Handle `next_cursor` until it is `null` or absent.
8. **Database and storage changes**
   - [ ] Migrate any task ID columns from integer to string/UUID.
   - [ ] Add `project_id` where you persist tasks.
9. **Testing and rollout**
   - [ ] Add/adjust unit tests to cover v2 structures and flows.
   - [ ] Run integration tests against a v2 environment.
   - [ ] Roll out changes gradually and monitor for 4xx errors (401, 404, 422).

---

## Upgrade command

Run the following to upgrade your Zrb CLI to v2:

```bash
zrb upgrade --major
```
