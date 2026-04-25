# Migrating from Zrb CLI v1 to v2

This guide helps you migrate your applications from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication—all of which require code changes.

## Overview of Breaking Changes

| Change | Impact |
|--------|--------|
| Endpoint prefix | All API paths now include `/v2/` |
| Authentication header | `X-Auth-Token` → `Authorization: Bearer` |
| Task ID type | Integer → UUID string |
| Task field rename | `done` → `completed` |
| Task creation | `project_id` now required |
| List response format | Bare array → Paginated envelope |

---

## Breaking Change #1: Endpoint Prefix

All endpoints are now prefixed with `/v2/`. This affects every API call.

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

### Code Example (JavaScript)
```javascript
// v1
const response = await fetch('/tasks');

// v2
const response = await fetch('/v2/tasks');
```

---

## Breaking Change #2: Authentication Header

The authentication header has changed from `X-Auth-Token` to the standard Bearer token format. Requests using the old header will receive HTTP 401.

### Before (v1)
```bash
X-Auth-Token: your_api_key
```

### After (v2)
```bash
Authorization: Bearer your_api_token
```

### Code Example (JavaScript)
```javascript
// v1
const response = await fetch('/v2/tasks', {
  headers: {
    'X-Auth-Token': apiKey
  }
});

// v2
const response = await fetch('/v2/tasks', {
  headers: {
    'Authorization': `Bearer ${apiKey}`
  }
});
```

### Code Example (Python)
```python
# v1
headers = {'X-Auth-Token': api_key}

# v2
headers = {'Authorization': f'Bearer {api_key}'}
```

---

## Breaking Change #3: Task ID Type

Task IDs have changed from integers to UUID strings. This affects how you store, compare, and use task IDs.

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

### Code Example (JavaScript)
```javascript
// v1 - storing as number
const taskId = 42;
const url = `/v2/tasks/${taskId}`;

// v2 - storing as string
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
const url = `/v2/tasks/${taskId}`;
```

### Code Example (Python)
```python
# v1 - storing as int
task_id = 42
url = f"/v2/tasks/{task_id}"

# v2 - storing as string
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
url = f"/v2/tasks/{task_id}"
```

### Database Migration Note
If you're storing task IDs in your database, you'll need to:
1. Change the column type from `INTEGER` to `VARCHAR(36)` or `UUID`
2. Update any foreign key references
3. Migrate existing integer IDs to UUIDs (you may need to maintain a mapping table)

---

## Breaking Change #4: Task Field Rename (`done` → `completed`)

The `done` field has been renamed to `completed`. This affects both request bodies and response parsing.

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

### Code Example (JavaScript)
```javascript
// v1 - reading response
const task = await response.json();
if (task.done) {
  console.log('Task is complete');
}

// v2 - reading response
const task = await response.json();
if (task.completed) {
  console.log('Task is complete');
}

// v1 - updating task
await fetch(`/v2/tasks/${taskId}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ done: true })
});

// v2 - updating task
await fetch(`/v2/tasks/${taskId}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ completed: true })
});
```

### Code Example (Python)
```python
# v1 - reading response
task = response.json()
if task['done']:
    print('Task is complete')

# v2 - reading response
task = response.json()
if task['completed']:
    print('Task is complete')

# v1 - updating task
requests.put(f'/v2/tasks/{task_id}', json={'done': True})

# v2 - updating task
requests.put(f'/v2/tasks/{task_id}', json={'completed': True})
```

---

## Breaking Change #5: Task Creation Requires `project_id`

Creating a task now requires a `project_id` field. Omitting it will result in HTTP 422.

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

### Code Example (JavaScript)
```javascript
// v1
const response = await fetch('/v2/tasks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${apiKey}`
  },
  body: JSON.stringify({
    title: 'New task title'
  })
});

// v2
const response = await fetch('/v2/tasks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${apiKey}`
  },
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123'
  })
});
```

### Code Example (Python)
```python
# v1
response = requests.post(
    '/v2/tasks',
    headers={'Authorization': f'Bearer {api_key}'},
    json={'title': 'New task title'}
)

# v2
response = requests.post(
    '/v2/tasks',
    headers={'Authorization': f'Bearer {api_key}'},
    json={
        'title': 'New task title',
        'project_id': 'proj_abc123'
    }
)
```

### Getting a Project ID
You'll need to obtain a valid `project_id` before creating tasks. This typically involves:
1. Creating a project via the Projects API (if not already exists)
2. Storing the project ID for reuse
3. Passing it with every task creation request

---

## Breaking Change #6: List Response Format

List endpoints now return a paginated envelope instead of a bare array. This affects how you iterate through results.

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
    {"id": "b2c3d4e5-f6g7-8901-bcde-f12345678901", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

### Code Example (JavaScript)
```javascript
// v1 - simple array iteration
const tasks = await response.json();
tasks.forEach(task => {
  console.log(task.title);
});

// v2 - envelope with pagination
const data = await response.json();
const tasks = data.items;
const total = data.total;
const nextCursor = data.next_cursor;

tasks.forEach(task => {
  console.log(task.title);
});

// v2 - fetching all pages
async function fetchAllTasks() {
  let allTasks = [];
  let cursor = null;

  do {
    const url = cursor ? `/v2/tasks?cursor=${cursor}` : '/v2/tasks';
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await response.json();
    allTasks = allTasks.concat(data.items);
    cursor = data.next_cursor;
  } while (cursor);

  return allTasks;
}
```

### Code Example (Python)
```python
# v1 - simple array iteration
tasks = response.json()
for task in tasks:
    print(task['title'])

# v2 - envelope with pagination
data = response.json()
tasks = data['items']
total = data['total']
next_cursor = data['next_cursor']

for task in tasks:
    print(task['title'])

# v2 - fetching all pages
def fetch_all_tasks():
    all_tasks = []
    cursor = None

    while True:
        url = f'/v2/tasks?cursor={cursor}' if cursor else '/v2/tasks'
        response = requests.get(url, headers={'Authorization': f'Bearer {api_key}'})
        data = response.json()
        all_tasks.extend(data['items'])
        cursor = data.get('next_cursor')
        if not cursor:
            break

    return all_tasks
```

### Pagination Parameters
- `cursor`: Pagination cursor from previous response's `next_cursor`
- `limit`: Maximum results per page (default: 20)

---

## Migration Checklist

Use this checklist to ensure you've addressed all breaking changes:

### Authentication
- [ ] Update all API calls to use `Authorization: Bearer <token>` instead of `X-Auth-Token`
- [ ] Remove any hardcoded `X-Auth-Token` headers
- [ ] Test authentication with a sample request

### Endpoints
- [ ] Update all endpoint URLs to include `/v2/` prefix
- [ ] Update any hardcoded endpoint paths in configuration files
- [ ] Verify all API calls use the new endpoint structure

### Task IDs
- [ ] Update data models/types to use string/UUID instead of integer for task IDs
- [ ] Update database schema if storing task IDs locally
- [ ] Update any ID validation logic
- [ ] Update URL path construction for task-specific endpoints

### Task Fields
- [ ] Rename all references from `done` to `completed` in request bodies
- [ ] Rename all references from `done` to `completed` in response parsing
- [ ] Update any UI labels or display logic
- [ ] Update any filtering/sorting logic that uses this field

### Task Creation
- [ ] Add `project_id` to all task creation requests
- [ ] Implement logic to obtain/validate project IDs
- [ ] Update any forms or UI to collect project ID
- [ ] Handle HTTP 422 errors for missing `project_id`

### List Responses
- [ ] Update list response parsing to extract `items` array
- [ ] Update any code that expects a bare array
- [ ] Implement pagination logic using `next_cursor`
- [ ] Update any UI that displays total counts (use `total` field)

### Testing
- [ ] Test all CRUD operations (Create, Read, Update, Delete)
- [ ] Test pagination with multiple pages
- [ ] Test error handling for invalid authentication
- [ ] Test error handling for missing `project_id`
- [ ] Run integration tests with the v2 API

### Documentation
- [ ] Update API documentation references
- [ ] Update any developer guides or tutorials
- [ ] Update code comments referencing v1 behavior
- [ ] Communicate changes to your team

---

## Upgrade Command

To upgrade to Zrb CLI v2, run:

```bash
npm install -g @zrb/cli@latest
```

Or if using a package manager:

```bash
# yarn
yarn global add @zrb/cli@latest

# pnpm
pnpm add -g @zrb/cli@latest
```

After upgrading, verify your installation:

```bash
zrb --version
```

You should see output indicating version 2.x.x.

---

## Need Help?

If you encounter issues during migration:
- Check the [v2 API Reference](./v2_spec.md) for detailed endpoint documentation
- Review error messages carefully—they often indicate which breaking change is causing the issue
- Test changes incrementally rather than all at once
- Keep v1 available as a fallback during the migration period

---

## Additional Resources

- [v1 API Reference](./v1_spec.md) - For comparison during migration
- [v2 API Reference](./v2_spec.md) - Complete v2 documentation
- [Project API Documentation](./projects.md) - For managing projects and obtaining `project_id` values