# Migrating from Zrb CLI v1 to v2

This guide helps you migrate your code from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication—all of which require changes to your existing code.

## Overview of Breaking Changes

1. **Endpoint paths**: All endpoints now require `/v2/` prefix
2. **Authentication**: Header changed from `X-Auth-Token` to `Authorization: Bearer`
3. **Task IDs**: Changed from integer to UUID string
4. **Task status field**: `done` renamed to `completed`
5. **Task creation**: Now requires `project_id`
6. **List responses**: Changed from bare array to paginated envelope

---

## Breaking Change 1: Endpoint Paths

All API endpoints now include a `/v2/` prefix. Requests to v1 endpoints will return 404.

### Before (v1)
```bash
GET /tasks
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

### After (v2)
```bash
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Code Example
```javascript
// v1
const response = await fetch('https://api.zrb.io/tasks');

// v2
const response = await fetch('https://api.zrb.io/v2/tasks');
```

---

## Breaking Change 2: Authentication Header

The authentication header format has changed. The old `X-Auth-Token` header is no longer accepted and will return HTTP 401.

### Before (v1)
```http
X-Auth-Token: your_api_key
```

### After (v2)
```http
Authorization: Bearer your_api_token
```

### Code Example
```javascript
// v1
const headers = {
  'X-Auth-Token': apiKey
};

// v2
const headers = {
  'Authorization': `Bearer ${apiToken}`
};
```

---

## Breaking Change 3: Task ID Type

Task IDs are now UUID strings instead of integers. This affects how you store, compare, and use task IDs in your code.

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
```javascript
// v1
const taskId = 42;
const url = `/tasks/${taskId}`;

// v2
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
const url = `/v2/tasks/${taskId}`;
```

**Note**: If you stored task IDs as integers in your database, you'll need to migrate your schema to use string/UUID types.

---

## Breaking Change 4: Task Status Field

The `done` field has been renamed to `completed`. This affects both request bodies and response parsing.

### Before (v1)
```json
{
  "title": "Updated title",
  "done": true
}
```

### After (v2)
```json
{
  "title": "Updated title",
  "completed": true
}
```

### Code Example
```javascript
// v1
const task = await response.json();
if (task.done) {
  console.log('Task is complete');
}

// v2
const task = await response.json();
if (task.completed) {
  console.log('Task is complete');
}
```

---

## Breaking Change 5: Task Creation Requires Project ID

Creating a task now requires a `project_id` field. Omitting it returns HTTP 422 Unprocessable Entity.

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
```javascript
// v1
await fetch('/tasks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'New task' })
});

// v2
await fetch('/v2/tasks', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ 
    title: 'New task',
    project_id: 'proj_abc123'
  })
});
```

**Note**: You'll need to obtain a valid `project_id` before creating tasks. Use the projects endpoint (not covered in v1 spec) to list available projects.

---

## Breaking Change 6: List Response Pagination

List endpoints no longer return a bare array. They now return a paginated envelope with `items`, `total`, and `next_cursor`.

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
```javascript
// v1
const tasks = await response.json();
tasks.forEach(task => console.log(task.title));

// v2
const data = await response.json();
const tasks = data.items;
const total = data.total;
const nextCursor = data.next_cursor;

tasks.forEach(task => console.log(task.title));

// Fetch next page
if (nextCursor) {
  const nextResponse = await fetch(`/v2/tasks?cursor=${nextCursor}`);
}
```

**Note**: The default page size is 20. Use the `limit` query parameter to adjust: `/v2/tasks?limit=50`.

---

## Migration Checklist

Use this checklist to ensure you've addressed all breaking changes:

- [ ] Update all endpoint URLs to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer`
- [ ] Update task ID storage and handling from integer to UUID string
- [ ] Rename all references to `done` field to `completed`
- [ ] Add `project_id` to all task creation requests
- [ ] Update list response parsing to handle paginated envelope
- [ ] Implement cursor-based pagination for list endpoints
- [ ] Update any database schemas storing task IDs to use string/UUID types
- [ ] Update test fixtures and mocks with new response formats
- [ ] Update API client libraries or SDKs with new signatures

---

## Upgrade Command

To upgrade to Zrb CLI v2, run:

```bash
npm install -g @zrb/cli@latest
# or
yarn global add @zrb/cli@latest
# or
pip install --upgrade zrb-cli
```

After upgrading, verify your installation:

```bash
zrb --version
```

You should see output indicating version 2.x.x.

---

## Need Help?

If you encounter issues during migration:
- Check the [v2 API reference](./v2_spec.md) for detailed endpoint documentation
- Review error messages carefully—v2 provides more specific validation errors
- Test your changes against a staging environment before production deployment