# Migrating from Zrb CLI v1 to v2

This guide helps you migrate your code from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication. All changes are breaking — you must update your code to continue using the API.

## Breaking Changes Overview

| Change | Impact |
|--------|--------|
| Endpoint prefix | All endpoints now require `/v2/` prefix |
| Authentication | Header changed from `X-Auth-Token` to `Authorization: Bearer` |
| Task ID type | Changed from integer to UUID string |
| Task field | `done` renamed to `completed` |
| Task creation | `project_id` is now required |
| List response | Returns paginated envelope instead of bare array |

---

## 1. Endpoint Prefix Change

All endpoints are now prefixed with `/v2/`. Update your base URL or endpoint paths.

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
const response = await fetch('https://api.zrb.io/tasks', {
  headers: { 'X-Auth-Token': apiKey }
});

// v2
const response = await fetch('https://api.zrb.io/v2/tasks', {
  headers: { 'Authorization': `Bearer ${apiToken}` }
});
```

---

## 2. Authentication Header Change

The authentication header changed from `X-Auth-Token` to `Authorization: Bearer`. Requests using the old header will receive HTTP 401.

### Before (v1)
```http
X-Auth-Token: your_api_key_here
```

### After (v2)
```http
Authorization: Bearer your_api_token_here
```

### Code Example
```javascript
// v1
headers: {
  'X-Auth-Token': 'sk_live_1234567890abcdef'
}

// v2
headers: {
  'Authorization': 'Bearer sk_live_1234567890abcdef'
}
```

---

## 3. Task ID Type Change

Task IDs changed from integer to UUID string. Update any code that stores, compares, or parses task IDs.

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

// If you were storing IDs in a database, migrate your schema:
// ALTER TABLE tasks ALTER COLUMN id TYPE UUID USING id::text;
```

---

## 4. Task Field Rename: `done` → `completed`

The `done` field was renamed to `completed`. Update all references in your code.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

### Code Example
```javascript
// v1
if (task.done) {
  console.log('Task is complete');
}

// v2
if (task.completed) {
  console.log('Task is complete');
}

// v1 - creating/updating
await fetch('/tasks/42', {
  method: 'PUT',
  body: JSON.stringify({ done: true })
});

// v2 - creating/updating
await fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  body: JSON.stringify({ completed: true })
});
```

---

## 5. Task Creation Requires `project_id`

Creating a task now requires a `project_id` field. Omitting it returns HTTP 422.

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
  headers: { 'X-Auth-Token': apiKey },
  body: JSON.stringify({ title: 'New task' })
});

// v2
await fetch('/v2/tasks', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${apiToken}` },
  body: JSON.stringify({
    title: 'New task',
    project_id: 'proj_abc123'
  })
});
```

**Note**: You'll need to obtain a valid `project_id` before creating tasks. Use the projects endpoint (if available) or your dashboard to find your project IDs.

---

## 6. List Response Format Change

List endpoints now return a paginated envelope instead of a bare array. Update your list handling code.

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
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

### Code Example
```javascript
// v1
const response = await fetch('/tasks');
const tasks = await response.json();
tasks.forEach(task => console.log(task.title));

// v2
const response = await fetch('/v2/tasks');
const data = await response.json();
const tasks = data.items;
tasks.forEach(task => console.log(task.title));

// v2 - with pagination
let allTasks = [];
let cursor = null;

do {
  const url = cursor ? `/v2/tasks?cursor=${cursor}` : '/v2/tasks';
  const response = await fetch(url);
  const data = await response.json();
  allTasks = allTasks.concat(data.items);
  cursor = data.next_cursor;
} while (cursor);

console.log(`Total tasks: ${data.total}`);
```

---

## Migration Checklist

Follow this checklist to migrate your codebase:

- [ ] Update base URL or all endpoint paths to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer` in all requests
- [ ] Update database schema or data types to store UUID strings instead of integers for task IDs
- [ ] Rename all references from `done` to `completed` in request bodies and response parsing
- [ ] Add `project_id` to all task creation requests
- [ ] Update list endpoint handling to parse paginated envelope (`data.items` instead of bare array)
- [ ] Implement pagination logic using `next_cursor` if you need to fetch all results
- [ ] Update any ID comparisons or validations to handle UUID strings
- [ ] Test all CRUD operations (create, read, update, delete)
- [ ] Verify authentication works with new header format
- [ ] Update any error handling for HTTP 422 (missing `project_id`)

---

## Upgrade Command

To upgrade your Zrb CLI installation:

```bash
# Using npm
npm install -g @zrb/cli@latest

# Using Homebrew (macOS)
brew upgrade zrb

# Using pip
pip install --upgrade zrb-cli

# Using curl (Linux/macOS)
curl -sSL https://get.zrb.io | sh
```

After upgrading, verify your installation:

```bash
zrb --version
# Should output: zrb v2.0.0 or higher
```

---

## Need Help?

- Review the [v2 API reference](./v2_spec.md) for complete endpoint documentation
- Check the [v1 API reference](./v1_spec.md) if you need to reference old behavior
- Open an issue on GitHub for migration questions or bugs