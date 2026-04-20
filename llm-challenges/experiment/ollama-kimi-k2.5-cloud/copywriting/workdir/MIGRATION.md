# Zrb CLI v1 → v2 Migration Guide

This guide helps you migrate your applications from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication. Several breaking changes require code updates.

---

## Breaking Changes

### 1. API Version Prefix

All endpoints are now prefixed with `/v2/`. v1 endpoints will return 404.

**Before (v1):**
```bash
curl https://api.zrb.io/tasks
```

**After (v2):**
```bash
curl https://api.zrb.io/v2/tasks
```

---

### 2. Authentication Header

The authentication header has changed from `X-Auth-Token` to `Authorization: Bearer`. Requests using the old header will receive HTTP 401.

**Before (v1):**
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.io/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.io/v2/tasks
```

---

### 3. Task ID Type

Task IDs changed from integers to UUID strings. Update any code that assumes integer IDs.

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
// v1: ID is an integer
const taskId = 42;
fetch(`/tasks/${taskId}`);
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
// v2: ID is a UUID string
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
fetch(`/v2/tasks/${taskId}`);
```

---

### 4. Task Field `done` Renamed to `completed`

The boolean field indicating task completion has been renamed from `done` to `completed`.

**Before (v1):**
```javascript
// Creating a task
fetch("/tasks", {
  method: "POST",
  headers: { "X-Auth-Token": token },
  body: JSON.stringify({ title: "Write tests" })
});

// Updating a task
fetch("/tasks/42", {
  method: "PUT",
  headers: { "X-Auth-Token": token },
  body: JSON.stringify({ done: true })
});

// Reading task status
const isComplete = task.done;
```

**After (v2):**
```javascript
// Creating a task (note: project_id now required)
fetch("/v2/tasks", {
  method: "POST",
  headers: { "Authorization": `Bearer ${token}` },
  body: JSON.stringify({ title: "Write tests", project_id: "proj_abc123" })
});

// Updating a task
fetch("/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890", {
  method: "PUT",
  headers: { "Authorization": `Bearer ${token}` },
  body: JSON.stringify({ completed: true })
});

// Reading task status
const isComplete = task.completed;
```

---

### 5. `project_id` Required on Task Creation

Tasks must now belong to a project. Creating a task without `project_id` returns HTTP 422.

**Before (v1):**
```json
POST /tasks
{
  "title": "New task title"
}
```

```python
# Python example
response = requests.post(
    "https://api.zrb.io/tasks",
    headers={"X-Auth-Token": api_key},
    json={"title": "New task"}
)
```

**After (v2):**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

```python
# Python example
response = requests.post(
    "https://api.zrb.io/v2/tasks",
    headers={"Authorization": f"Bearer {api_token}"},
    json={"title": "New task", "project_id": "proj_abc123"}
)
```

---

### 6. List Endpoints Return Paginated Envelope

`GET /tasks` no longer returns a bare array. It now returns a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**
```json
GET /tasks

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
// v1: Direct array access
const tasks = await response.json();
tasks.forEach(task => console.log(task.title));
```

**After (v2):**
```json
GET /v2/tasks

{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v2", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// v2: Access items from envelope
const data = await response.json();
const tasks = data.items;
tasks.forEach(task => console.log(task.title));

// Fetch next page
if (data.next_cursor) {
  fetch(`/v2/tasks?cursor=${data.next_cursor}`);
}
```

---

## Migration Checklist

Use this checklist to ensure a complete migration:

- [ ] Update all API endpoint URLs to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>` header
- [ ] Update Task ID handling to expect UUID strings instead of integers
- [ ] Replace all references to `task.done` with `task.completed` in request bodies and response parsing
- [ ] Add `project_id` to all task creation requests
- [ ] Update list tasks response handling to parse the paginated envelope (`items`, `total`, `next_cursor`)
- [ ] Implement pagination support using `cursor` and `next_cursor` for list endpoints
- [ ] Update database schemas if you store task IDs (change integer columns to string/varchar)
- [ ] Update API client libraries and regenerate types
- [ ] Test all integrations in a staging environment before production deployment

---

## Upgrade Command

Update your CLI to v2:

```bash
zrb self-update --version 2.0.0
```

---

## Need Help?

- Review the full [v2 API specification](v2_spec.md)
- Check the [v1 specification](v1_spec.md) for comparison
- Join our developer community Discord for migration support
