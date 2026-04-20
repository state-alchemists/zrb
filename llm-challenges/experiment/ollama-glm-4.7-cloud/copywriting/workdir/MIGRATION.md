# Zrb CLI v1 → v2 Migration Guide

This guide helps you migrate your code from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication—all of which require changes to your existing code.

## Overview of Breaking Changes

1. **Authentication header** — Changed from `X-Auth-Token` to Bearer token
2. **Endpoint prefix** — All endpoints now require `/v2/` prefix
3. **Task ID type** — Changed from integer to UUID string
4. **Task field rename** — `done` → `completed`
5. **Task creation** — Now requires `project_id`
6. **List response format** — Changed from bare array to paginated envelope

---

## Breaking Change #1: Authentication Header

### What Changed

The authentication header has changed from a custom header to the standard Bearer token format.

### Before (v1)

```bash
curl -X GET https://api.zrb.io/tasks \
  -H "X-Auth-Token: your_api_key"
```

```javascript
// JavaScript/Node.js
const response = await fetch('https://api.zrb.io/tasks', {
  headers: {
    'X-Auth-Token': 'your_api_key'
  }
});
```

```python
# Python
headers = {'X-Auth-Token': 'your_api_key'}
response = requests.get('https://api.zrb.io/tasks', headers=headers)
```

### After (v2)

```bash
curl -X GET https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer your_api_token"
```

```javascript
// JavaScript/Node.js
const response = await fetch('https://api.zrb.io/v2/tasks', {
  headers: {
    'Authorization': 'Bearer your_api_token'
  }
});
```

```python
# Python
headers = {'Authorization': 'Bearer your_api_token'}
response = requests.get('https://api.zrb.io/v2/tasks', headers=headers)
```

### Impact

All API calls will return **HTTP 401** if you continue using `X-Auth-Token`.

---

## Breaking Change #2: Endpoint Prefix

### What Changed

All endpoints now require a `/v2/` prefix. This allows v1 and v2 to coexist during the transition period.

### Before (v1)

```bash
GET    /tasks
GET    /tasks/{id}
POST   /tasks
PUT    /tasks/{id}
DELETE /tasks/{id}
```

### After (v2)

```bash
GET    /v2/tasks
GET    /v2/tasks/{id}
POST   /v2/tasks
PUT    /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

### Impact

All endpoints will return **HTTP 404** if you omit the `/v2/` prefix.

---

## Breaking Change #3: Task ID Type

### What Changed

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

```javascript
// JavaScript/Node.js
const taskId = 42;
const response = await fetch(`https://api.zrb.io/tasks/${taskId}`);
```

```python
# Python
task_id = 42
response = requests.get(f'https://api.zrb.io/tasks/{task_id}')
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

```javascript
// JavaScript/Node.js
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
const response = await fetch(`https://api.zrb.io/v2/tasks/${taskId}`);
```

```python
# Python
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
response = requests.get(f'https://api.zrb.io/v2/tasks/{task_id}')
```

### Impact

- Database schemas storing task IDs as integers must be updated to strings
- Type checking/validation code must accept UUID strings
- URL routing parameters must handle string IDs

---

## Breaking Change #4: Task Field Rename (`done` → `completed`)

### What Changed

The `done` field has been renamed to `completed` for clarity and consistency.

### Before (v1)

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
// JavaScript/Node.js
// Creating a task
await fetch('https://api.zrb.io/tasks', {
  method: 'POST',
  headers: {'X-Auth-Token': 'your_api_key'},
  body: JSON.stringify({title: 'New task'})
});

// Updating a task
await fetch('https://api.zrb.io/tasks/42', {
  method: 'PUT',
  headers: {'X-Auth-Token': 'your_api_key'},
  body: JSON.stringify({done: true})
});

// Reading a task
const task = await response.json();
if (task.done) {
  console.log('Task is complete');
}
```

```python
# Python
# Creating a task
requests.post('https://api.zrb.io/tasks',
    headers={'X-Auth-Token': 'your_api_key'},
    json={'title': 'New task'})

# Updating a task
requests.put('https://api.zrb.io/tasks/42',
    headers={'X-Auth-Token': 'your_api_key'},
    json={'done': True})

# Reading a task
task = response.json()
if task['done']:
    print('Task is complete')
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

```javascript
// JavaScript/Node.js
// Creating a task
await fetch('https://api.zrb.io/v2/tasks', {
  method: 'POST',
  headers: {'Authorization': 'Bearer your_api_token'},
  body: JSON.stringify({
    title: 'New task',
    project_id: 'proj_abc123'
  })
});

// Updating a task
await fetch('https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  headers: {'Authorization': 'Bearer your_api_token'},
  body: JSON.stringify({completed: true})
});

// Reading a task
const task = await response.json();
if (task.completed) {
  console.log('Task is complete');
}
```

```python
# Python
# Creating a task
requests.post('https://api.zrb.io/v2/tasks',
    headers={'Authorization': 'Bearer your_api_token'},
    json={
        'title': 'New task',
        'project_id': 'proj_abc123'
    })

# Updating a task
requests.put('https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    headers={'Authorization': 'Bearer your_api_token'},
    json={'completed': True})

# Reading a task
task = response.json()
if task['completed']:
    print('Task is complete')
```

### Impact

- All references to `done` in request bodies and response parsing must be updated to `completed`
- Frontend UI code displaying task status must use the new field name
- Database queries filtering by `done` must be updated

---

## Breaking Change #5: Task Creation Requires `project_id`

### What Changed

Creating a task now requires a `project_id` field. This enables better organization and project-based task management.

### Before (v1)

```bash
curl -X POST https://api.zrb.io/tasks \
  -H "X-Auth-Token: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task title"}'
```

```javascript
// JavaScript/Node.js
const response = await fetch('https://api.zrb.io/tasks', {
  method: 'POST',
  headers: {
    'X-Auth-Token': 'your_api_key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'New task title'
  })
});
```

```python
# Python
response = requests.post('https://api.zrb.io/tasks',
    headers={'X-Auth-Token': 'your_api_key'},
    json={'title': 'New task title'})
```

### After (v2)

```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New task title",
    "project_id": "proj_abc123"
  }'
```

```javascript
// JavaScript/Node.js
const response = await fetch('https://api.zrb.io/v2/tasks', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your_api_token',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123'
  })
});
```

```python
# Python
response = requests.post('https://api.zrb.io/v2/tasks',
    headers={'Authorization': 'Bearer your_api_token'},
    json={
        'title': 'New task title',
        'project_id': 'proj_abc123'
    })
```

### Impact

- Task creation requests without `project_id` will return **HTTP 422**
- You must obtain a valid `project_id` before creating tasks
- Existing code that creates tasks needs to be updated to include project context

---

## Breaking Change #6: List Response Format (Pagination)

### What Changed

List endpoints now return a paginated envelope instead of a bare array. This enables efficient pagination for large datasets.

### Before (v1)

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
// JavaScript/Node.js
const response = await fetch('https://api.zrb.io/tasks', {
  headers: {'X-Auth-Token': 'your_api_key'}
});
const tasks = await response.json();
tasks.forEach(task => console.log(task.title));
```

```python
# Python
response = requests.get('https://api.zrb.io/tasks',
    headers={'X-Auth-Token': 'your_api_key'})
tasks = response.json()
for task in tasks:
    print(task['title'])
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

```javascript
// JavaScript/Node.js
const response = await fetch('https://api.zrb.io/v2/tasks', {
  headers: {'Authorization': 'Bearer your_api_token'}
});
const data = await response.json();
const tasks = data.items;
tasks.forEach(task => console.log(task.title));

// Pagination
if (data.next_cursor) {
  const nextPage = await fetch(`https://api.zrb.io/v2/tasks?cursor=${data.next_cursor}`, {
    headers: {'Authorization': 'Bearer your_api_token'}
  });
}
```

```python
# Python
response = requests.get('https://api.zrb.io/v2/tasks',
    headers={'Authorization': 'Bearer your_api_token'})
data = response.json()
tasks = data['items']
for task in tasks:
    print(task['title'])

# Pagination
if data.get('next_cursor'):
    next_page = requests.get('https://api.zrb.io/v2/tasks',
        params={'cursor': data['next_cursor']},
        headers={'Authorization': 'Bearer your_api_token'})
```

### Impact

- Code expecting a bare array will break
- You must access `data.items` to get the task list
- Pagination logic should use `next_cursor` for subsequent pages
- `total` field provides the total count across all pages

---

## Migration Checklist

Use this checklist to ensure you've addressed all breaking changes:

### Authentication & Endpoints
- [ ] Update all authentication headers from `X-Auth-Token` to `Authorization: Bearer <token>`
- [ ] Add `/v2/` prefix to all endpoint URLs
- [ ] Test authentication with the new header format

### Data Types & Fields
- [ ] Update database schema to store task IDs as strings (UUIDs)
- [ ] Update type definitions/interfaces to use string IDs
- [ ] Replace all references to `done` with `completed`
- [ ] Update UI code to display `completed` field
- [ ] Update form validation to accept `completed` instead of `done`

### Task Creation
- [ ] Obtain valid `project_id` values for your use cases
- [ ] Update task creation code to include `project_id`
- [ ] Add error handling for HTTP 422 when `project_id` is missing

### List Responses & Pagination
- [ ] Update list response parsing to access `data.items`
- [ ] Update code that iterates over task lists
- [ ] Implement pagination using `next_cursor`
- [ ] Update UI to display total count from `total` field

### Testing
- [ ] Run integration tests against v2 endpoints
- [ ] Test all CRUD operations (Create, Read, Update, Delete)
- [ ] Test pagination with multiple pages
- [ ] Test error scenarios (missing auth, invalid IDs, missing project_id)
- [ ] Verify frontend displays correctly with new field names

### Deployment
- [ ] Update environment variables if API base URL is stored there
- [ ] Update API client libraries or SDKs
- [ ] Deploy changes to staging environment first
- [ ] Monitor logs for 401, 404, and 422 errors
- [ ] Roll back plan if issues arise

---

## Upgrade Command

To upgrade your Zrb CLI installation to v2:

```bash
# Using npm
npm install -g @zrb/cli@latest

# Using yarn
yarn global add @zrb/cli@latest

# Using Homebrew (macOS)
brew upgrade zrb

# Using pip
pip install --upgrade zrb-cli

# Verify the version
zrb --version
```

After upgrading, test your integration with the v2 API:

```bash
# Test authentication
curl -X GET https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer your_api_token"

# Expected response: paginated envelope with your tasks
```

---

## Need Help?

- **Documentation**: [https://docs.zrb.io](https://docs.zrb.io)
- **API Reference**: [https://api.zrb.io/docs](https://api.zrb.io/docs)
- **Support**: [support@zrb.io](mailto:support@zrb.io)
- **GitHub Issues**: [https://github.com/zrb/cli/issues](https://github.com/zrb/cli/issues)