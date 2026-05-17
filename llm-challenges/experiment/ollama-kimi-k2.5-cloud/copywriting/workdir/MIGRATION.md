# Migrating from Zrb CLI v1 to v2

This guide covers all breaking changes when upgrading from v1 to v2. Review each section and update your code accordingly.

---

## Breaking Change 1: API Version Prefix

All endpoints are now prefixed with `/v2/`.

**Before (v1):**
```bash
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**
```bash
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Breaking Change 2: Authentication Header

The authentication header changed from `X-Auth-Token` to Bearer token format.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" \
  https://api.zrb.io/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" \
  https://api.zrb.io/v2/tasks
```

Requests with `X-Auth-Token` will receive HTTP 401.

---

## Breaking Change 3: Task ID Type

Task IDs changed from integers to UUID strings.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
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

Update any code that assumes integer IDs.

---

## Breaking Change 4: Field Rename: `done` → `completed`

The task status field has been renamed from `done` to `completed`.

**Before (v1):**
```json
// Request body
{
  "title": "Updated title",
  "done": true
}

// Response
{
  "id": 42,
  "title": "Updated title",
  "done": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2):**
```json
// Request body
{
  "title": "Updated title",
  "completed": true
}

// Response
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Updated title",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Breaking Change 5: Task Creation Requires `project_id`

Creating a task now requires a `project_id` field.

**Before (v1):**
```bash
curl -X POST https://api.zrb.io/tasks \
  -H "X-Auth-Token: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

**After (v2):**
```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New task",
    "project_id": "proj_abc123"
  }'
```

Omitting `project_id` will return HTTP 422.

---

## Breaking Change 6: List Endpoints Return Paginated Envelope

List endpoints no longer return bare arrays. They now return a paginated envelope.

**Before (v1):**
```bash
curl https://api.zrb.io/tasks \
  -H "X-Auth-Token: your_api_key"
```

**Response:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```bash
curl "https://api.zrb.io/v2/tasks?limit=20" \
  -H "Authorization: Bearer your_api_token"
```

**Response:**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "uuid-2", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Pagination:** Pass `?cursor=<next_cursor>` to fetch subsequent pages.

---

## Complete Example Migration

Here's a full before/after comparison for a typical integration:

**Before (v1):**
```javascript
// Config
const API_KEY = process.env.ZRB_API_KEY;
const BASE_URL = 'https://api.zrb.io';

// List tasks
const response = await fetch(`${BASE_URL}/tasks`, {
  headers: { 'X-Auth-Token': API_KEY }
});
const tasks = await response.json();  // Array of tasks

// Create task
await fetch(`${BASE_URL}/tasks`, {
  method: 'POST',
  headers: { 'X-Auth-Token': API_KEY, 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'New task' })
});

// Update task
await fetch(`${BASE_URL}/tasks/${taskId}`, {
  method: 'PUT',
  headers: { 'X-Auth-Token': API_KEY, 'Content-Type': 'application/json' },
  body: JSON.stringify({ done: true })
});
```

**After (v2):**
```javascript
// Config
const API_TOKEN = process.env.ZRB_API_TOKEN;
const BASE_URL = 'https://api.zrb.io';

// List tasks (handle pagination)
const response = await fetch(`${BASE_URL}/v2/tasks`, {
  headers: { 'Authorization': `Bearer ${API_TOKEN}` }
});
const data = await response.json();
const tasks = data.items;  // Tasks are in `items` array
const hasMore = !!data.next_cursor;

// Create task (project_id required)
await fetch(`${BASE_URL}/v2/tasks`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${API_TOKEN}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ 
    title: 'New task',
    project_id: 'proj_abc123'  // Required
  })
});

// Update task (field renamed)
await fetch(`${BASE_URL}/v2/tasks/${taskId}`, {
  method: 'PUT',
  headers: { 'Authorization': `Bearer ${API_TOKEN}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ completed: true })  // Field is now `completed`
});
```

---

## Migration Checklist

Use this checklist to ensure a complete migration:

- [ ] Update all API URLs to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] Update any variable typed as `number` for task IDs to `string` (UUID format)
- [ ] Rename all references to `task.done` to `task.completed`
- [ ] Add `project_id` to all task creation payloads
- [ ] Update list task response handling to extract items from `response.items`
- [ ] Implement pagination cursor handling for list endpoints
- [ ] Update test assertions that rely on integer IDs or response structure
- [ ] Verify error handling (new HTTP 422 for missing `project_id`)
- [ ] Update environment variable names (`ZRB_API_KEY` → `ZRB_API_TOKEN` recommended)

---

## Upgrade Command

Install v2 via your package manager:

```bash
npm install -g zrb@2.0.0
# or
yarn global add zrb@2.0.0
# or
pip install zrb==2.0.0
```

---

*Need help? Open an issue at https://github.com/zrb/zrb/issues*
