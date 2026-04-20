# Zrb CLI v1 → v2 Migration Guide

This guide helps you migrate your code from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication—all of which require code changes.

## Overview of Breaking Changes

| Change | Impact |
|--------|--------|
| Endpoint prefix | All URLs now require `/v2/` prefix |
| Authentication header | `X-Auth-Token` → `Authorization: Bearer` |
| Task ID type | Integer → UUID string |
| Task field rename | `done` → `completed` |
| Task creation | `project_id` now required |
| List response format | Bare array → Paginated envelope |

---

## 1. Endpoint Prefix Change

**Breaking Change:** All endpoints are now prefixed with `/v2/`.

### Before (v1)
```bash
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

### After (v2)
```bash
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Code Example

**Before:**
```javascript
const response = await fetch('https://api.zrb.io/tasks');
```

**After:**
```javascript
const response = await fetch('https://api.zrb.io/v2/tasks');
```

---

## 2. Authentication Header Change

**Breaking Change:** The authentication header changed from `X-Auth-Token` to `Authorization: Bearer`.

### Before (v1)
```http
X-Auth-Token: your_api_key_here
```

### After (v2)
```http
Authorization: Bearer your_api_token_here
```

### Code Example

**Before:**
```javascript
const headers = {
  'X-Auth-Token': apiKey,
  'Content-Type': 'application/json'
};
```

**After:**
```javascript
const headers = {
  'Authorization': `Bearer ${apiToken}`,
  'Content-Type': 'application/json'
};
```

**Note:** Requests using `X-Auth-Token` will receive HTTP 401 Unauthorized.

---

## 3. Task ID Type Change

**Breaking Change:** Task IDs changed from integer to UUID string. This affects all endpoints that reference a task ID.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Code Example

**Before:**
```javascript
// Storing task ID
const taskId = 42;

// Fetching a task
const response = await fetch(`/tasks/${taskId}`);
```

**After:**
```javascript
// Storing task ID
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";

// Fetching a task
const response = await fetch(`/v2/tasks/${taskId}`);
```

**Impact:** If you store task IDs in databases or local storage, you'll need to migrate those values to UUIDs.

---

## 4. Task Field Rename: `done` → `completed`

**Breaking Change:** The `done` field was renamed to `completed`. This affects both request bodies and response parsing.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Code Example

**Before:**
```javascript
// Creating a task
const response = await fetch('/tasks', {
  method: 'POST',
  headers: { 'X-Auth-Token': apiKey },
  body: JSON.stringify({ title: 'New task' })
});

// Updating task status
await fetch(`/tasks/${id}`, {
  method: 'PUT',
  headers: { 'X-Auth-Token': apiKey },
  body: JSON.stringify({ done: true })
});

// Checking task status
if (task.done) {
  console.log('Task is complete');
}
```

**After:**
```javascript
// Creating a task
const response = await fetch('/v2/tasks', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${apiToken}` },
  body: JSON.stringify({ 
    title: 'New task',
    project_id: 'proj_abc123'
  })
});

// Updating task status
await fetch(`/v2/tasks/${id}`, {
  method: 'PUT',
  headers: { 'Authorization': `Bearer ${apiToken}` },
  body: JSON.stringify({ completed: true })
});

// Checking task status
if (task.completed) {
  console.log('Task is complete');
}
```

---

## 5. Task Creation Requires `project_id`

**Breaking Change:** Creating a task now requires a `project_id` field. Omitting it returns HTTP 422 Unprocessable Entity.

### Before (v1)
```json
{
  "title": "New task title"
}
```

### After (v2)
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Code Example

**Before:**
```javascript
const newTask = await fetch('/tasks', {
  method: 'POST',
  headers: { 'X-Auth-Token': apiKey },
  body: JSON.stringify({ title: 'Write documentation' })
});
```

**After:**
```javascript
const newTask = await fetch('/v2/tasks', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${apiToken}` },
  body: JSON.stringify({ 
    title: 'Write documentation',
    project_id: 'proj_abc123'
  })
});
```

**Note:** You'll need to obtain a valid `project_id` before creating tasks. Use the projects endpoint (if available) or contact your administrator.

---

## 6. List Response Format Change

**Breaking Change:** List endpoints now return a paginated envelope instead of a bare array.

### Before (v1)
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2)
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-f6g7-8901-bcde-f23456789012", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

### Code Example

**Before:**
```javascript
const response = await fetch('/tasks', {
  headers: { 'X-Auth-Token': apiKey }
});
const tasks = await response.json();

// tasks is an array
tasks.forEach(task => {
  console.log(task.title, task.done);
});
```

**After:**
```javascript
const response = await fetch('/v2/tasks', {
  headers: { 'Authorization': `Bearer ${apiToken}` }
});
const data = await response.json();

// data.items is the array
data.items.forEach(task => {
  console.log(task.title, task.completed);
});

// Pagination
if (data.next_cursor) {
  const nextPage = await fetch(`/v2/tasks?cursor=${data.next_cursor}`, {
    headers: { 'Authorization': `Bearer ${apiToken}` }
  });
}
```

**Pagination Parameters:**
- `cursor` — pagination cursor (optional)
- `limit` — max results per page, default 20

---

## Migration Checklist

Use this checklist to ensure you've addressed all breaking changes:

### Authentication
- [ ] Update all request headers from `X-Auth-Token` to `Authorization: Bearer`
- [ ] Verify your API token works with the new auth format

### Endpoints
- [ ] Add `/v2/` prefix to all endpoint URLs
- [ ] Update GET, POST, PUT, DELETE endpoint paths

### Task IDs
- [ ] Update code that stores/references task IDs to use UUID strings
- [ ] Migrate any database fields storing task IDs to UUID type
- [ ] Update URL path parameters for task-specific endpoints

### Task Fields
- [ ] Rename all references from `done` to `completed` in request bodies
- [ ] Rename all references from `done` to `completed` in response parsing
- [ ] Update any UI labels or display logic

### Task Creation
- [ ] Add `project_id` to all task creation requests
- [ ] Obtain valid `project_id` values for your use cases
- [ ] Handle HTTP 422 errors for missing `project_id`

### List Responses
- [ ] Update list response parsing to access `data.items` instead of `data`
- [ ] Implement pagination using `next_cursor`
- [ ] Update any code that expects a bare array from list endpoints

### Testing
- [ ] Run integration tests against v2 endpoints
- [ ] Verify all CRUD operations work correctly
- [ ] Test pagination behavior
- [ ] Validate error handling for 401 and 422 responses

---

## Upgrade Command

To upgrade your Zrb CLI to v2, run:

```bash
npm install -g @zrb/cli@latest
# or
yarn global add @zrb/cli@latest
# or
pip install --upgrade zrb-cli
```

After upgrading, verify your version:

```bash
zrb --version
# Should output: zrb v2.x.x
```

---

## Need Help?

If you encounter issues during migration:
- Check the [v2 API Reference](./v2_spec.md) for detailed endpoint documentation
- Review the [v1 API Reference](./v1_spec.md) to compare with your current implementation
- Contact support at support@zrb.io with your migration questions
- Join our [Discord community](https://discord.gg/zrb) for peer support

---

## Additional Resources

- [v2 API Reference](./v2_spec.md) — Complete v2 endpoint documentation
- [v1 API Reference](./v1_spec.md) — Legacy v1 documentation (for reference only)
- [Changelog](./CHANGELOG.md) — Full list of changes between versions