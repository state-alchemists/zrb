# Zrb Task API Migration Guide: v1 → v2

This guide covers all breaking changes when upgrading from v1 to v2. The v2 release introduces projects, pagination, and a stricter authentication model.

---

## Breaking Changes Overview

| Change | v1 | v2 |
|--------|----|----|
| Endpoint prefix | `/tasks` | `/v2/tasks` |
| Authentication header | `X-Auth-Token` | `Authorization: Bearer` |
| Task ID type | integer | UUID string |
| Task status field | `done` | `completed` |
| Task creation | `project_id` optional | `project_id` **required** |
| List response | bare array | paginated envelope |

---

## 1. Authentication Header

The authentication header has changed from a custom header to standard Bearer token authentication.

**Breaking change:** Requests using `X-Auth-Token` will receive HTTP 401 Unauthorized.

### Before (v1)

```bash
curl -H "X-Auth-Token: your_api_key" https://api.example.com/tasks
```

```javascript
// JavaScript
fetch('/tasks', {
  headers: {
    'X-Auth-Token': apiKey
  }
});
```

```python
# Python
import requests

headers = {'X-Auth-Token': api_key}
response = requests.get('https://api.example.com/tasks', headers=headers)
```

### After (v2)

```bash
curl -H "Authorization: Bearer your_api_token" https://api.example.com/v2/tasks
```

```javascript
// JavaScript
fetch('/v2/tasks', {
  headers: {
    'Authorization': `Bearer ${apiToken}`
  }
});
```

```python
# Python
import requests

headers = {'Authorization': f'Bearer {api_token}'}
response = requests.get('https://api.example.com/v2/tasks', headers=headers)
```

---

## 2. Endpoint Prefix

All endpoints are now prefixed with `/v2/`.

**Breaking change:** v1 endpoints will return HTTP 404.

### Before (v1)

```bash
GET /tasks
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

### After (v2)

```bash
GET /v2/tasks
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

## 3. Task ID Type Change

Task IDs have changed from auto-increment integers to UUID strings.

**Breaking change:** Any code parsing, storing, or validating IDs as integers will fail.

### Before (v1)

```json
{
  "id": 42,
  "title": "Write tests"
}
```

```javascript
// JavaScript - Integer validation
if (typeof task.id === 'number') {
  // ...
}

// URL construction with integer
const url = `/tasks/${taskId}`;
```

```python
# Python - Integer type hints
def get_task(task_id: int) -> dict:
    return requests.get(f'/tasks/{task_id}').json()
```

### After (v2)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

```javascript
// JavaScript - String validation
if (typeof task.id === 'string') {
  // ...
}

// URL construction works the same
const url = `/v2/tasks/${taskId}`;
```

```python
# Python - UUID/string type hints
def get_task(task_id: str) -> dict:
    return requests.get(f'/v2/tasks/{task_id}').json()
```

---

## 4. Field Rename: `done` → `completed`

The `done` field has been renamed to `completed` for clarity.

**Breaking change:** Code referencing `done` will fail. The v2 API will reject `done` in request bodies.

### Before (v1)

```json
// Task object
{
  "id": 1,
  "title": "Buy milk",
  "done": false
}
```

```bash
# Update task
curl -X PUT /tasks/1 -d '{"done": true}'
```

```javascript
// JavaScript
if (task.done) {
  console.log('Task completed!');
}

// Update request
await fetch(`/tasks/${id}`, {
  method: 'PUT',
  body: JSON.stringify({ done: true })
});
```

```python
# Python
if task['done']:
    print('Task completed!')

# Update request
requests.put(f'/tasks/{id}', json={'done': True})
```

### After (v2)

```json
// Task object
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Buy milk",
  "completed": false
}
```

```bash
# Update task
curl -X PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 -d '{"completed": true}'
```

```javascript
// JavaScript
if (task.completed) {
  console.log('Task completed!');
}

// Update request
await fetch(`/v2/tasks/${id}`, {
  method: 'PUT',
  body: JSON.stringify({ completed: true })
});
```

```python
# Python
if task['completed']:
    print('Task completed!')

# Update request
requests.put(f'/v2/tasks/{id}', json={'completed': True})
```

---

## 5. Required `project_id` on Task Creation

Creating a task now requires a `project_id` field.

**Breaking change:** Creating a task without `project_id` will return HTTP 422 Unprocessable Entity.

### Before (v1)

```bash
curl -X POST /tasks -d '{"title": "New task title"}'
```

```javascript
// JavaScript
const task = await fetch('/tasks', {
  method: 'POST',
  body: JSON.stringify({ title: 'New task title' })
});
```

```python
# Python
task = requests.post('/tasks', json={'title': 'New task title'})
```

### After (v2)

```bash
curl -X POST /v2/tasks -d '{"title": "New task title", "project_id": "proj_abc123"}'
```

```javascript
// JavaScript
const task = await fetch('/v2/tasks', {
  method: 'POST',
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123'
  })
});
```

```python
# Python
task = requests.post('/v2/tasks', json={
    'title': 'New task title',
    'project_id': 'proj_abc123'
})
```

---

## 6. Paginated List Response

List endpoints now return a paginated envelope with metadata instead of a bare array.

**Breaking change:** Code expecting a direct array will need to access `.items` and handle pagination.

### Before (v1)

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
// JavaScript
const tasks = await fetch('/tasks').then(r => r.json());
tasks.forEach(task => console.log(task.title));
```

```python
# Python
tasks = requests.get('/tasks').json()
for task in tasks:
    print(task['title'])
```

### After (v2)

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc", "created_at": "..."},
    {"id": "b2c3...", "title": "Ship v1", "completed": true, "project_id": "proj_abc", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// JavaScript - Access items from envelope
const response = await fetch('/v2/tasks').then(r => r.json());
response.items.forEach(task => console.log(task.title));

// Pagination
if (response.next_cursor) {
  const nextPage = await fetch(`/v2/tasks?cursor=${response.next_cursor}`);
}
```

```python
# Python - Access items from envelope
response = requests.get('/v2/tasks').json()
for task in response['items']:
    print(task['title'])

# Pagination
if response['next_cursor']:
    next_page = requests.get(f"/v2/tasks?cursor={response['next_cursor']}")
```

---

## 7. Task Object Structure

The v2 task object includes a new field and a renamed field.

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

---

## Migration Checklist

Follow these steps in order:

- [ ] **1. Update authentication headers**
  - Change `X-Auth-Token` to `Authorization: Bearer <token>`
  - Verify all API clients use the new header

- [ ] **2. Update API endpoint URLs**
  - Add `/v2` prefix to all endpoints
  - Update base URLs in configuration files

- [ ] **3. Update ID handling**
  - Change task ID type from `int` to `str` (or UUID)
  - Update database schemas if storing IDs
  - Update validation logic for UUID format

- [ ] **4. Rename `done` to `completed`**
  - Update all code reading `task.done` → `task.completed`
  - Update all API request bodies using `done` → `completed`
  - Update database column names if applicable

- [ ] **5. Add `project_id` to task creation**
  - Update all task creation calls to include `project_id`
  - Implement project selection UI if needed
  - Ensure project IDs are available before creating tasks

- [ ] **6. Update list response handling**
  - Change array access to `.items` property access
  - Implement pagination logic using `next_cursor` and `limit`
  - Update any `total` count references (now in envelope)

- [ ] **7. Update tests and integration suites**
  - Mock responses with v2 format
  - Add tests for pagination
  - Add tests for auth header changes

- [ ] **8. Monitor for HTTP 401/404/422 errors**
  - Set up alerts for authentication failures
  - Log endpoint mismatches for quick identification

---

## Upgrade Command

```bash
npm install zrb-task-api-client@2.0.0
# or
pip install zrb-task-api-client==2.0.0
```

---

## Support

For questions or issues with migration:
- GitHub Issues: https://github.com/zrb/task-api/issues
- Discord: https://discord.gg/zrb-dev