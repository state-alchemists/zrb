# Zrb Task API — v1 to v2 Migration Guide

Zrb Task API v2 introduces projects, proper pagination, stricter authentication, and a cleaner data model. The following changes are **all breaking** — your existing v1 clients will not work against a v2 server without the updates described below.

**Estimated migration time:** 30–60 minutes for a typical client.

---

## Breaking Changes

### 1. Endpoint Prefix — `/v2/`

All endpoints are now served under `/v2/`. Requests to bare `/tasks` will fail.

**Before (v1):**

```
GET /tasks
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**

```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

### 2. Authentication Header — Bearer Token

The `X-Auth-Token` header has been replaced by the standard `Authorization: Bearer` scheme. Requests using `X-Auth-Token` receive HTTP 401.

**Before (v1):**

```
X-Auth-Token: <your_api_key>
```

**After (v2):**

```
Authorization: Bearer <your_api_token>
```

---

### 3. Task ID — Integer to UUID String

The `id` field on task objects has changed from an auto-incrementing integer to a UUID v4 string. All endpoint path parameters that reference a task ID must use the new format.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
// v1 client code
const taskId = response.data.id;    // number
const type = typeof taskId;         // "number"
```

**After (v2):**

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
// v2 client code
const taskId = response.data.id;    // string (UUID)
const type = typeof taskId;         // "string"
```

---

### 4. Field Rename — `done` to `completed`

The boolean status field has been renamed from `done` to `completed`. This affects both request bodies when creating or updating tasks and response payloads.

**Before (v1):**

```json
// Request body — update task
{
  "done": true
}
```

```javascript
// v1 response access
if (task.done) {
  console.log("Task is complete");
}
```

**After (v2):**

```json
// Request body — update task
{
  "completed": true
}
```

```javascript
// v2 response access
if (task.completed) {
  console.log("Task is complete");
}
```

---

### 5. Required Field — `project_id`

Task creation now requires a `project_id` field. Omitting it returns HTTP 422. You must obtain a valid project ID before creating tasks.

**Before (v1):**

```json
// POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**

```json
// POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

### 6. List Endpoints — Paginated Envelope

All list endpoints return a paginated envelope instead of a bare array. The response now includes `items`, `total`, and `next_cursor` fields. Use the cursor to fetch subsequent pages.

**Before (v1):**

```json
// GET /tasks
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true,  "created_at": "..."}
]
```

```javascript
// v1: iterate directly
tasks.forEach(t => console.log(t.title));
```

**After (v2):**

```json
// GET /v2/tasks
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "c3d4...", "title": "Ship v2",  "completed": true,  "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// v2: unwrap the envelope
const tasks = response.data.items;
tasks.forEach(t => console.log(t.title));

// Paginate
while (response.data.next_cursor) {
  response = await fetch(`/v2/tasks?cursor=${response.data.next_cursor}`);
  response.data.items.forEach(t => console.log(t.title));
}
```

---

## Migration Checklist

- [ ] **Update endpoint URLs** — Prepend `/v2/` to every API path.
- [ ] **Replace auth header** — Change `X-Auth-Token` to `Authorization: Bearer <token>`.
- [ ] **Change ID type handling** — Task IDs are now UUID strings. Update any type checks, comparison operators, or database columns that assumed integers.
- [ ] **Rename `done` to `completed`** — Update all request bodies and response parsing that reference the status field.
- [ ] **Add `project_id` to task creation** — Determine the target project ID and include `project_id` in every `POST /v2/tasks` body.
- [ ] **Unwrap list responses** — Access `response.items` instead of the root array. Handle pagination with the `next_cursor` / `cursor` mechanism.
- [ ] **Update type definitions** — If your client uses TypeScript, OpenAPI schemas, or hand-rolled types, update them to match the v2 Task Object shape.
- [ ] **Run smoke tests** — Exercise each endpoint (`GET`, `POST`, `PUT`, `DELETE`) against v2 before cutting over in production.

---

## Upgrade Command

```bash
pip install zrb-cli>=2.0.0
```
