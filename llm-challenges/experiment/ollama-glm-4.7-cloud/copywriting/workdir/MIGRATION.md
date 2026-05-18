# Migrating from Zrb CLI v1 to v2

This guide helps you migrate your existing code from Zrb Task API v1 to v2. All v1 endpoints will be deprecated on **2024-06-01**.

## Overview of Breaking Changes

| Change | Impact |
|--------|--------|
| All endpoints now require `/v2/` prefix | URL updates required |
| Authentication header changed | `X-Auth-Token` → `Authorization: Bearer` |
| Task `id` changed from integer to UUID | Data model and API calls affected |
| Field `done` renamed to `completed` | Request/response parsing updates |
| `project_id` now required for task creation | Additional input required |
| List responses are paginated envelopes | Response parsing logic changes |

---

## 1. Endpoint URLs

All v1 endpoints now require the `/v2/` prefix.

### v1
```bash
GET /tasks
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

### v2
```bash
GET /v2/tasks
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

## 2. Authentication

The authentication header has changed from a custom header to the standard Bearer token format.

### v1
```javascript
headers: {
  'X-Auth-Token': 'your_api_key_here'
}
```

### v2
```javascript
headers: {
  'Authorization': 'Bearer your_api_token_here'
}
```

**Note:** Requests using `X-Auth-Token` will receive HTTP 401 Unauthorized.

---

## 3. Task ID Format

Task IDs have changed from integers to UUID strings. This affects both API responses and request parameters.

### v1 Task Object
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### v2 Task Object
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Code Example: Updating a Task

#### v1
```javascript
fetch('/tasks/42', {
  method: 'PUT',
  headers: { 'X-Auth-Token': 'your_api_key_here' },
  body: JSON.stringify({ done: true })
});
```

#### v2
```javascript
fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  headers: { 'Authorization': 'Bearer your_api_token_here' },
  body: JSON.stringify({ completed: true })
});
```

---

## 4. Field Rename: `done` → `completed`

The `done` field has been renamed to `completed`. All requests and responses must use the new field name.

### v1 Request
```javascript
fetch('/tasks/42', {
  method: 'PUT',
  body: JSON.stringify({ done: true })
});
```

### v2 Request
```javascript
fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  body: JSON.stringify({ completed: true })
});
```

### v1 Response Parsing
```javascript
const task = await response.json();
if (task.done) {
  console.log('Task is done');
}
```

### v2 Response Parsing
```javascript
const task = await response.json();
if (task.completed) {
  console.log('Task is completed');
}
```

---

## 5. Required `project_id` for Task Creation

Creating a task now requires specifying a `project_id`. Omitting it returns HTTP 422 Unprocessable Entity.

### v1
```javascript
fetch('/tasks', {
  method: 'POST',
  headers: { 'X-Auth-Token': 'your_api_key_here' },
  body: JSON.stringify({
    title: 'New task title'
  })
});
```

### v2
```javascript
fetch('/v2/tasks', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer your_api_token_here' },
  body: JSON.stringify({
    title: 'New task title',
    project_id: 'proj_abc123'  // Required
  })
});
```

**Note:** You'll need to obtain a valid `project_id` before creating tasks. Check for a project list endpoint or use your project ID from the dashboard.

---

## 6. Paginated List Responses

List endpoints no longer return bare arrays. They now return a paginated envelope with `items`, `total`, and `next_cursor`.

### v1 Response
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### v2 Response
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-f6a7-8901-bcde-f23456789012", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

### Code Example: Fetching All Tasks

#### v1
```javascript
const response = await fetch('/tasks', {
  headers: { 'X-Auth-Token': 'your_api_key_here' }
});
const tasks = await response.json();
```

#### v2
```javascript
async function fetchAllTasks() {
  let allTasks = [];
  let cursor = null;

  do {
    const url = cursor ? `/v2/tasks?cursor=${cursor}` : '/v2/tasks';
    const response = await fetch(url, {
      headers: { 'Authorization': 'Bearer your_api_token_here' }
    });
    const data = await response.json();
    allTasks = allTasks.concat(data.items);
    cursor = data.next_cursor;
  } while (cursor);

  return allTasks;
}
```

You can also use the `limit` query param (default 20) to control page size:

```javascript
fetch('/v2/tasks?limit=50', {
  headers: { 'Authorization': 'Bearer your_api_token_here' }
});
```

---

## Migration Checklist

Follow this step-by-step checklist to migrate your application:

1. [ ] **Update authentication headers**
   - Replace `X-Auth-Token` with `Authorization: Bearer <token>`

2. [ ] **Update all endpoint URLs**
   - Add `/v2/` prefix to all API calls
   - Update hardcoded URLs in config files

3. [ ] **Update data model for Task**
   - Change `id` type from integer to string (UUID)
   - Rename field `done` to `completed`
   - Add `project_id` field to Task model

4. [ ] **Update task creation logic**
   - Pass `project_id` when creating tasks
   - Handle 422 errors if `project_id` is missing

5. [ ] **Update list endpoint handling**
   - Parse envelope response (`data.items` instead of bare array)
   - Implement cursor-based pagination if you fetch multiple pages

6. [ ] **Update update/delete operations**
   - Use UUID-based task IDs instead of integers
   - Use `completed` instead of `done` in request bodies

7. [ ] **Update response parsing**
   - Access `completed` instead of `done`
   - Handle UUID strings for IDs

8. [ ] **Test all CRUD operations**
   - Create: verify `project_id` is included
   - Read: verify UUID IDs are handled correctly
   - Update: verify `completed` field updates
   - List: verify pagination envelope parsing
   - Delete: verify UUID-based deletion works

9. [ ] **Run integration tests**
   - Ensure all existing tests pass with v2 changes
   - Test edge cases (pagination, missing required fields)

10. [ ] **Update documentation**
    - Document the new endpoint structure
    - Update code examples and snippets
    - Update API client libraries if maintained

---

## Upgrade Command

Upgrading the Zrb CLI will automatically switch your API client to use v2 endpoints:

```bash
# For npm
npm update @zrb/cli

# For Homebrew
brew upgrade zrb

# For pip
pip install --upgrade zrb
```

**Important:** After upgrading, verify your application works correctly. v1 endpoints will be deprecated on **2024-06-01** and will no longer function after that date.

---

## Need Help?

If you encounter issues during migration:

- Check the [v2 API Reference](./v2_spec.md) for detailed endpoint documentation
- Review the [v1 API Reference](./v1_spec.md) to compare old behavior
- Contact support with error codes and request/response payloads