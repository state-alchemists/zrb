# Zrb CLI v1 → v2 Migration Guide

This guide helps you migrate your code from Zrb CLI v1 to v2. v2 introduces projects, pagination, and stricter authentication with several breaking changes that require code updates.

---

## Breaking Changes

### 1. Endpoint Prefix Added

All API endpoints are now prefixed with `/v2/`.

**Before (v1):**
```bash
curl https://api.zrb.io/tasks
curl https://api.zrb.io/tasks/42
```

**After (v2):**
```bash
curl https://api.zrb.io/v2/tasks
curl https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication Header Changed

The authentication header format has changed from custom header to Bearer token.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" \
  https://api.zrb.io/tasks
```

```javascript
// JavaScript example
fetch('/tasks', {
  headers: { 'X-Auth-Token': apiKey }
});
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" \
  https://api.zrb.io/v2/tasks
```

```javascript
// JavaScript example
fetch('/v2/tasks', {
  headers: { 'Authorization': `Bearer ${apiToken}` }
});
```

**Note:** Requests using `X-Auth-Token` will now receive HTTP 401 Unauthorized.

---

### 3. Task ID Changed from Integer to UUID

Task IDs are now UUID strings instead of auto-incrementing integers.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

```javascript
// v1 treated IDs as numbers
const taskId = 42;
fetch(`/tasks/${taskId}`);
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

```javascript
// v2 IDs are UUID strings
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
fetch(`/v2/tasks/${taskId}`);
```

---

### 4. Field `done` Renamed to `completed`

The boolean field indicating task completion status has been renamed.

**Before (v1):**
```json
{
  "id": 1,
  "title": "Ship v1",
  "done": true
}
```

```javascript
// Creating a task
fetch('/tasks', {
  method: 'POST',
  body: JSON.stringify({ title: 'New task', done: false })
});

// Updating a task
fetch('/tasks/42', {
  method: 'PUT',
  body: JSON.stringify({ done: true })
});
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v2",
  "completed": true
}
```

```javascript
// Creating a task (note: project_id now required, see below)
fetch('/v2/tasks', {
  method: 'POST',
  body: JSON.stringify({ title: 'New task', project_id: 'proj_abc123' })
});

// Updating a task
fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  body: JSON.stringify({ completed: true })
});
```

---

### 5. Task Creation Requires `project_id`

Creating a task now requires a `project_id` field. Requests without it return HTTP 422.

**Before (v1):**
```bash
curl -X POST https://api.zrb.io/tasks \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your_api_key" \
  -d '{"title": "New task"}'
```

```javascript
fetch('/tasks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Auth-Token': apiKey
  },
  body: JSON.stringify({ title: 'New task' })
});
```

**After (v2):**
```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_token" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

```javascript
fetch('/v2/tasks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${apiToken}`
  },
  body: JSON.stringify({ 
    title: 'New task',
    project_id: 'proj_abc123'
  })
});
```

---

### 6. List Endpoints Return Paginated Envelope

The `GET /tasks` endpoint no longer returns a bare array. It now returns a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
const tasks = await fetch('/tasks').then(r => r.json());
tasks.forEach(task => console.log(task.title));
```

**After (v2):**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false, "created_at": "...", "project_id": "..."},
    {"id": "uuid-2", "title": "Ship v2", "completed": true, "created_at": "...", "project_id": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

```javascript
const response = await fetch('/v2/tasks').then(r => r.json());
const tasks = response.items; // Access items array
tasks.forEach(task => console.log(task.title));

// Pagination
const nextPage = await fetch('/v2/tasks?cursor=' + response.next_cursor).then(r => r.json());
```

---

## Migration Checklist

Follow these steps to migrate your code:

- [ ] **Install v2 CLI**: Run the upgrade command (see below)
- [ ] **Update API tokens**: Ensure you have a valid Bearer token for v2 (old API keys may require regeneration)
- [ ] **Update base URL**: Add `/v2` prefix to all endpoint URLs in your integration
- [ ] **Update authentication**: Replace `X-Auth-Token` header with `Authorization: Bearer <token>` header
- [ ] **Update ID handling**: Change task ID variables from integers to strings (UUIDs) throughout your codebase
- [ ] **Update field names**: Search and replace `done` with `completed` in request/response handling
- [ ] **Add project_id**: Update task creation to include `project_id` field
- [ ] **Update list parsing**: Change list endpoint response handling from direct array access to `response.items`
- [ ] **Add pagination support**: Optionally implement cursor-based pagination for task lists
- [ ] **Test thoroughly**: Verify all CRUD operations work with v2 before deploying to production
- [ ] **Update documentation**: Inform your team about API changes and update any internal API docs

---

## Upgrade to v2

To upgrade your CLI:

```bash
zrb upgrade --to v2
```

After upgrading, verify the version:

```bash
zrb --version  # Should display v2.x.x
```

---

## Need Help?

If you encounter issues during migration:

1. Consult the v2 spec in `v2_spec.md`
2. Check that your bearer tokens are valid in the v2 dashboard
3. Ensure you're using UUID strings for all task IDs
4. Verify `project_id` is included in all task creation requests
