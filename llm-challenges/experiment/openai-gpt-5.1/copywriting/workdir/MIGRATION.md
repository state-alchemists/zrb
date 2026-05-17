# Zrb Task API v1 → v2 Migration Guide

This guide walks through all breaking changes between the Zrb Task API v1 and v2, with concrete before/after examples and a practical migration checklist.

The audience is teams already integrated with the v1 HTTP API.

---

## 1. Versioned Endpoints (`/tasks` → `/v2/tasks`)

### What changed

All task endpoints are now explicitly versioned under the `/v2/` prefix:

- v1: `/tasks`, `/tasks/{id}`
- v2: `/v2/tasks`, `/v2/tasks/{id}`

Unversioned v1 paths will not receive v2 behaviour.

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

### Migration notes

- Update any hard-coded paths, API client base URLs, and OpenAPI/SDK definitions to use `/v2/`.
- If you support both versions during rollout, keep v1 calls on `/tasks` and v2 calls on `/v2/tasks` side-by-side.

---

## 2. Authentication Header (`X-Auth-Token` → `Authorization: Bearer`)

### What changed

Authentication moved from a custom header to a standard Bearer token:

- v1: `X-Auth-Token: <your_api_key>`
- v2: `Authorization: Bearer <your_api_token>`

Requests that still send `X-Auth-Token` will receive HTTP `401 Unauthorized` under v2.

### Before (v1)

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: v1_abc123
```

### After (v2)

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer v2_abc123
```

### Example: JavaScript fetch wrapper

Before:

```js
async function listTasksV1() {
  const res = await fetch('https://api.example.com/tasks', {
    headers: {
      'X-Auth-Token': process.env.ZRB_API_KEY,
    },
  });
  return res.json();
}
```

After:

```js
async function listTasksV2() {
  const res = await fetch('https://api.example.com/v2/tasks', {
    headers: {
      Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
    },
  });
  const body = await res.json();
  return body.items; // see pagination section
}
```

### Migration notes

- Rotate or provision new v2 tokens if they differ from v1 keys.
- Update any shared HTTP client middleware or interceptors that inject auth headers.

---

## 3. Task ID Type (integer → UUID string)

### What changed

Task `id` values are now UUID strings instead of integers:

- v1: `id: 42` (integer)
- v2: `id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"` (string)

This affects:

- Response payloads
- URL path parameters (`/v2/tasks/{id}`)
- Any local storage, database columns, or type definitions that assume numeric IDs

### Before (v1 response example)

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2 response example)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Example: Type migration (TypeScript)

Before:

```ts
// v1 types
type TaskV1 = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};

function getTaskUrlV1(task: TaskV1): string {
  return `/tasks/${task.id}`;
}
```

After:

```ts
// v2 types
type TaskV2 = {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
};

function getTaskUrlV2(task: TaskV2): string {
  return `/v2/tasks/${task.id}`;
}
```

### Migration notes

- Update type annotations (TypeScript, Flow, Java, Go structs, DB schemas) to use string IDs.
- Remove any numeric sorting or arithmetic on `id` values; treat them as opaque identifiers.

---

## 4. Task Completion Flag (`done` → `completed`)

### What changed

The boolean field representing task completion has been renamed:

- v1: `done`
- v2: `completed`

Both read and write payloads must use the new field name.

### Before (v1 task object)

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

Before (v1 update request):

```http
PUT /tasks/42 HTTP/1.1
Content-Type: application/json

{
  "done": true
}
```

### After (v2 task object)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

After (v2 update request):

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Content-Type: application/json

{
  "completed": true
}
```

### Example: Model and mapping change (Python)

Before:

```python
# v1 model
@dataclass
class TaskV1:
  id: int
  title: str
  done: bool
  created_at: str


def mark_done_v1(task_id: int) -> None:
  requests.put(
    f"https://api.example.com/tasks/{task_id}",
    json={"done": True},
    headers={"X-Auth-Token": API_KEY},
  )
```

After:

```python
# v2 model
@dataclass
class TaskV2:
  id: str
  title: str
  completed: bool
  project_id: str
  created_at: str


def mark_completed_v2(task_id: str) -> None:
  requests.put(
    f"https://api.example.com/v2/tasks/{task_id}",
    json={"completed": True},
    headers={"Authorization": f"Bearer {API_TOKEN}"},
  )
```

### Migration notes

- Search your codebase for `done` usage related to tasks and rename fields, DTOs, and mappings to `completed`.
- Be careful not to rename unrelated variables that happen to be called `done`.

---

## 5. Required `project_id` on Task Creation

### What changed

Task creation now requires associating a task with a project via `project_id`:

- v1: only `title` was required
- v2: `title` and `project_id` are required

Omitting `project_id` in v2 returns HTTP `422 Unprocessable Entity`.

### Before (v1 create)

```http
POST /tasks HTTP/1.1
Content-Type: application/json
X-Auth-Token: v1_abc123

{
  "title": "New task title"
}
```

### After (v2 create)

```http
POST /v2/tasks HTTP/1.1
Content-Type: application/json
Authorization: Bearer v2_abc123

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Example: Backend integration change (Node.js)

Before:

```js
// v1: only title
async function createTaskV1(title) {
  const res = await fetch('https://api.example.com/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': process.env.ZRB_API_KEY,
    },
    body: JSON.stringify({ title }),
  });
  return res.json();
}
```

After:

```js
// v2: title + project_id
async function createTaskV2(title, projectId) {
  const res = await fetch('https://api.example.com/v2/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
    },
    body: JSON.stringify({ title, project_id: projectId }),
  });
  return res.json();
}
```

### Migration notes

- Decide how your system determines `project_id` (user selection, default project, mapping from existing entities).
- Update all call sites that create tasks to pass a valid `project_id`.

---

## 6. List Responses: Bare Array → Paginated Envelope

### What changed

`GET /v2/tasks` no longer returns a bare JSON array. All list endpoints now return a paginated envelope:

- v1: `Task[]`
- v2: `{ items: TaskV2[], total: number, next_cursor: string | null }`

### Before (v1 list)

```http
GET /tasks HTTP/1.1
X-Auth-Token: v1_abc123
```

Response:

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2 list)

```http
GET /v2/tasks HTTP/1.1
Authorization: Bearer v2_abc123
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
      "id": "b2c3d4e5-f6a7-8901-bcde-f234567890ab",
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

To fetch the next page, pass the `cursor` query parameter:

```http
GET /v2/tasks?cursor=cursor_xyz&limit=20 HTTP/1.1
Authorization: Bearer v2_abc123
```

### Example: Client-side change (TypeScript)

Before:

```ts
async function listTasksV1(): Promise<TaskV1[]> {
  const res = await fetch('https://api.example.com/tasks', {
    headers: { 'X-Auth-Token': API_KEY },
  });
  return res.json(); // directly an array
}
```

After:

```ts
type TaskListResponseV2 = {
  items: TaskV2[];
  total: number;
  next_cursor: string | null;
};

async function listTasksV2(cursor?: string): Promise<TaskListResponseV2> {
  const url = new URL('https://api.example.com/v2/tasks');
  if (cursor) url.searchParams.set('cursor', cursor);

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${API_TOKEN}` },
  });
  return res.json();
}

async function listAllTasksV2(): Promise<TaskV2[]> {
  const all: TaskV2[] = [];
  let cursor: string | null | undefined = undefined;

  do {
    const page = await listTasksV2(cursor ?? undefined);
    all.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);

  return all;
}
```

### Migration notes

- Update JSON parsing to read from `items` rather than assuming the root JSON is an array.
- If you only need a single page, just use `items` from the first response.
- If you previously implemented offset-based pagination client-side, migrate to cursor-based pagination using `next_cursor`.

---

## 7. Non-breaking but Important: Full v2 Task Shape

While not strictly additional breaking changes beyond the ones above, it may be useful to see the full side-by-side shape.

### v1 Task

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### v2 Task

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Step-by-step Migration Checklist

Use this checklist to migrate an existing v1 integration to v2 with minimal downtime.

1. Authentication
   - [ ] Obtain or confirm your v2-compatible API tokens.
   - [ ] Update HTTP client/middleware to send `Authorization: Bearer <your_api_token>`.
   - [ ] Remove any reliance on `X-Auth-Token` for v2 calls.

2. Endpoint paths
   - [ ] Change all task-related URLs from `/tasks` to `/v2/tasks`.
   - [ ] Update any generated API clients or OpenAPI specs to use the `/v2/` prefix.

3. Types and models
   - [ ] Update task `id` fields from integer to string/UUID in your models, DTOs, and database where applicable.
   - [ ] Rename the `done` field to `completed` in all task-related models and JSON mappings.
   - [ ] Add `project_id` as a required field for task creation in your domain models and validation.

4. Create/Update flows
   - [ ] Update all `POST /tasks` calls to `POST /v2/tasks` and include a valid `project_id`.
   - [ ] Update all `PUT /tasks/{id}` calls to `PUT /v2/tasks/{id}` and use `completed` instead of `done`.

5. List and pagination
   - [ ] Update parsing of list responses to handle `{ items, total, next_cursor }` instead of a bare array.
   - [ ] Implement cursor-based pagination where you previously relied on fetching all tasks at once.
   - [ ] Adjust any consumer code that expects `GET /tasks` to return an array.

6. Testing and validation
   - [ ] Add/update unit and integration tests to cover the new v2 behaviour (auth, IDs, fields, pagination).
   - [ ] Run tests against a staging or sandbox environment exposing v2.
   - [ ] Monitor logs for 401, 404, and 422 responses after switching clients to v2.

7. Cleanup
   - [ ] Remove legacy v1-specific code paths once all clients are confirmed to use v2.
   - [ ] Update internal documentation and runbooks to reference v2 only.

---

## Upgrade Command

To upgrade the Zrb CLI to v2, run:

```bash
zrb upgrade --version 2
```
