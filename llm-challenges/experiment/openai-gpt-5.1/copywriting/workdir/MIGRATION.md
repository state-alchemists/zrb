# Zrb Task API v1 → v2 Migration Guide

This guide walks through all breaking changes in the Zrb Task API v2 and shows how to update an existing v1 integration. It assumes you are already familiar with the v1 API.

---

## 1. Versioned Endpoint Paths (`/tasks` → `/v2/tasks`)

**What changed**  
All endpoints are now explicitly versioned under the `/v2/` prefix.

- v1: `/tasks`, `/tasks/{id}`
- v2: `/v2/tasks`, `/v2/tasks/{id}`

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

**Action:** Update every hard‑coded path from `/tasks` to `/v2/tasks` (and similarly for any other Zrb endpoints when they are introduced in v2).

---

## 2. Authentication Header (`X-Auth-Token` → `Authorization: Bearer`)

**What changed**  
Authentication has moved from a custom header to the standard Bearer token header.

- v1: `X-Auth-Token: <your_api_key>`
- v2: `Authorization: Bearer <your_api_token>`

Requests that still use `X-Auth-Token` will receive **HTTP 401** in v2.

### Before (v1)

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: v1_example_key
```

```js
// JavaScript (v1)
const res = await fetch('https://api.example.com/tasks', {
  headers: {
    'X-Auth-Token': process.env.ZRB_API_KEY,
  },
});
```

### After (v2)

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer v2_example_token
```

```js
// JavaScript (v2)
const res = await fetch('https://api.example.com/v2/tasks', {
  headers: {
    Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
  },
});
```

**Action:** Replace all uses of `X-Auth-Token` with `Authorization: Bearer <token>` and ensure you provision a v2‑compatible token.

---

## 3. Task Identifier Type (integer → UUID string)

**What changed**  
Task `id` values are now UUID strings instead of integers.

- v1: `id: 42` (integer)
- v2: `id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"` (string)

This affects URL path parameters, database schemas, and any type definitions.

### Before (v1)

**Response example:**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**TypeScript model (v1):**

```ts
export interface TaskV1 {
  id: number;
  title: string;
  done: boolean;
  created_at: string; // ISO 8601
}
```

**Using the id (v1):**

```ts
async function fetchTask(id: number): Promise<TaskV1> {
  const res = await fetch(`https://api.example.com/tasks/${id}`);
  return res.json();
}
```

### After (v2)

**Response example:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**TypeScript model (v2):**

```ts
export interface TaskV2 {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string; // ISO 8601
}
```

**Using the id (v2):**

```ts
async function fetchTask(id: string): Promise<TaskV2> {
  const res = await fetch(`https://api.example.com/v2/tasks/${id}`);
  return res.json();
}
```

**Action:**
- Change any numeric `id` types to string/UUID types.
- Update route builders and validators to treat `id` as a string.

---

## 4. Task Completion Field (`done` → `completed`)

**What changed**  
The boolean field indicating completion has been renamed from `done` to `completed`.

- v1: `done: boolean`
- v2: `completed: boolean`

This impacts both read and write paths (task payloads and any serialization/deserialization code).

### Before (v1)

**Task JSON:**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Update request (v1):**

```http
PUT /tasks/42 HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "done": true
}
```

**Consumer code (v1):**

```py
# Python v1 client
@dataclass
class TaskV1:
  id: int
  title: str
  done: bool
  created_at: str


if task.done:
    print("Task is complete")
```

### After (v2)

**Task JSON:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Update request (v2):**

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "completed": true
}
```

**Consumer code (v2):**

```py
# Python v2 client
@dataclass
class TaskV2:
  id: str
  title: str
  completed: bool
  project_id: str
  created_at: str


if task.completed:
    print("Task is complete")
```

**Action:** Search your codebase for the `done` property on Zrb tasks and rename it to `completed`. Be careful not to touch unrelated `done` fields.

---

## 5. Required `project_id` on Task Creation

**What changed**  
Tasks must now belong to a project at creation time. The `project_id` field is **required** in `POST /v2/tasks`.

Omitting `project_id` will result in **HTTP 422 Unprocessable Entity**.

### Before (v1)

**Create request (v1):**

```http
POST /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "New task title"
}
```

**Typical code (v1):**

```js
// No project context in v1
await fetch('https://api.example.com/tasks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Auth-Token': process.env.ZRB_API_KEY,
  },
  body: JSON.stringify({ title: 'New task title' }),
});
```

### After (v2)

**Create request (v2):**

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

**Typical code (v2):**

```js
// v2: tasks are scoped to a project
await fetch('https://api.example.com/v2/tasks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
  },
  body: JSON.stringify({
    title: 'New task title',
    project_id: currentProjectId,
  }),
});
```

**Action:**
- Decide how your application maps tasks to projects.
- Ensure you always pass a valid `project_id` when creating tasks.
- Update client‑side validation and server‑side tests to expect `422` when `project_id` is missing.

---

## 6. List Response Shape (bare array → paginated envelope)

**What changed**  
List endpoints now return a paginated envelope instead of a bare array.

- v1: `GET /tasks` returns `Task[]`
- v2: `GET /v2/tasks` returns `{ items: Task[], total: number, next_cursor: string | null }`

### Before (v1)

**HTTP response:**

```http
HTTP/1.1 200 OK
Content-Type: application/json

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**Consumer code (v1):**

```ts
// tasks is an array
const res = await fetch('https://api.example.com/tasks');
const tasks: TaskV1[] = await res.json();

for (const task of tasks) {
  console.log(task.title);
}
```

### After (v2)

**HTTP response:**

```http
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
      "id": "b2c3d4e5-f6a1-8907-bcda-fe2345678901",
      "title": "Ship v2",
      "completed": true,
      "project_id": "proj_def456",
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Consumer code (v2):**

```ts
interface TaskListV2 {
  items: TaskV2[];
  total: number;
  next_cursor: string | null;
}

const res = await fetch('https://api.example.com/v2/tasks?limit=20');
const page: TaskListV2 = await res.json();

for (const task of page.items) {
  console.log(task.title);
}

if (page.next_cursor) {
  const nextRes = await fetch(
    `https://api.example.com/v2/tasks?cursor=${encodeURIComponent(page.next_cursor)}`,
  );
  const nextPage: TaskListV2 = await nextRes.json();
  // ...
}
```

**Action:**
- Update all consumers of list endpoints to read from `items` instead of assuming the root is an array.
- Implement cursor‑based pagination using the `cursor` query param and `next_cursor` response field.

---

## 7. Endpoint-by-Endpoint Migration Summary

This section summarizes the concrete changes per endpoint.

### 7.1 List Tasks

- **Path:** `/tasks` → `/v2/tasks`
- **Auth:** `X-Auth-Token` → `Authorization: Bearer ...`
- **Response:** `Task[]` → `{ items: TaskV2[], total, next_cursor }`
- **New query params:** `cursor`, `limit`

**Before:**

```http
GET /tasks HTTP/1.1
X-Auth-Token: <your_api_key>
```

**After:**

```http
GET /v2/tasks?limit=20 HTTP/1.1
Authorization: Bearer <your_api_token>
```

### 7.2 Get Task

- **Path:** `/tasks/{id}` → `/v2/tasks/{id}`
- **Auth:** `X-Auth-Token` → `Authorization: Bearer ...`
- **Id type:** integer → UUID string
- **Field rename:** `done` → `completed`

**Before:**

```http
GET /tasks/42 HTTP/1.1
X-Auth-Token: <your_api_key>
```

**After:**

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Authorization: Bearer <your_api_token>
```

### 7.3 Create Task

- **Path:** `/tasks` → `/v2/tasks`
- **Auth:** `X-Auth-Token` → `Authorization: Bearer ...`
- **Required field:** new `project_id` is required
- **Id type:** response now uses UUID string

**Before:**

```http
POST /tasks HTTP/1.1
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "New task title"
}
```

**After:**

```http
POST /v2/tasks HTTP/1.1
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 7.4 Update Task

- **Path:** `/tasks/{id}` → `/v2/tasks/{id}`
- **Auth:** `X-Auth-Token` → `Authorization: Bearer ...`
- **Id type:** integer → UUID string
- **Field rename:** `done` → `completed`

**Before:**

```http
PUT /tasks/42 HTTP/1.1
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "Updated title",
  "done": true
}
```

**After:**

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "Updated title",
  "completed": true
}
```

### 7.5 Delete Task

- **Path:** `/tasks/{id}` → `/v2/tasks/{id}`
- **Auth:** `X-Auth-Token` → `Authorization: Bearer ...`
- **Id type:** integer → UUID string

**Before:**

```http
DELETE /tasks/42 HTTP/1.1
X-Auth-Token: <your_api_key>
```

**After:**

```http
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Authorization: Bearer <your_api_token>
```

---

## 8. Migration Checklist

Use this checklist to drive and validate your migration.

1. **Authentication**
   - [ ] Replace all `X-Auth-Token` headers with `Authorization: Bearer <your_api_token>`.
   - [ ] Rotate or provision tokens if v2 uses a different credential set.

2. **Endpoint Paths**
   - [ ] Update all Zrb API URLs from `/tasks` to `/v2/tasks` (including any hard‑coded paths and documentation).

3. **Identifier Types**
   - [ ] Change task `id` types from integer to string/UUID in models, DTOs, and database schemas where applicable.
   - [ ] Update any validation logic or route builders that assumed numeric IDs.

4. **Task Fields**
   - [ ] Rename all uses of the `done` field on Zrb tasks to `completed`.
   - [ ] Ensure update payloads use `"completed"` instead of `"done"`.

5. **Task Creation**
   - [ ] Decide how your app determines `project_id` for new tasks.
   - [ ] Add `project_id` to every `POST /v2/tasks` request body.
   - [ ] Adjust tests to expect HTTP 422 when `project_id` is missing.

6. **List Responses & Pagination**
   - [ ] Update consumers of list endpoints to read from `response.items` instead of assuming the root is an array.
   - [ ] Implement cursor‑based pagination using the `cursor` query param and `next_cursor` response field.

7. **End-to-End Verification**
   - [ ] Run your test suite against v2 and ensure all API tests pass.
   - [ ] Manually verify core flows: list tasks, view task, create, update, delete.
   - [ ] Monitor logs for 401/404/422 responses after migration.

---

## 9. Upgrade Command

Once your code changes are in place, upgrade the Zrb CLI to v2:

```bash
zrb upgrade --major
```
