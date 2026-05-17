# Zrb Task API v1 → v2 Migration Guide

v2 introduces projects, pagination, and stricter auth. This guide covers all breaking changes and provides code examples for each.

## Breaking Changes Overview

| Change | v1 | v2 |
|--------|----|----|
| Endpoint prefix | `/tasks` | `/v2/tasks` |
| Authentication | `X-Auth-Token` header | `Authorization: Bearer` header |
| Task ID type | integer | UUID string |
| Task status field | `done` | `completed` |
| Task creation | `project_id` optional | `project_id` required |
| List response | bare array | paginated envelope |

---

## 1. Endpoint Prefix

All task endpoints now require the `/v2/` prefix. Using v1 paths returns 404.

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

## 2. Authentication Header

The auth header changed from a custom header to standard Bearer token. Requests using `X-Auth-Token` receive HTTP 401.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.io/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.io/v2/tasks
```

---

## 3. Task ID Type Changed to UUID

Task IDs changed from auto-increment integers to UUIDs. Update any code that stores or validates IDs.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123"
}
```

If you're validating IDs client-side, update your patterns:

**Before (v1):**
```javascript
const isValidId = (id) => Number.isInteger(id) && id > 0;
```

**After (v2):**
```javascript
const isValidId = (id) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
```

---

## 4. Field Renamed: `done` → `completed`

The task status field is now `completed` instead of `done`.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Buy milk",
  "done": false
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Buy milk",
  "completed": false,
  "project_id": "proj_abc123"
}
```

Update request bodies:

**Before (v1):**
```bash
curl -X PUT /tasks/42 -d '{"done": true}'
```

**After (v2):**
```bash
curl -X PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer your_api_token" \
  -d '{"completed": true}'
```

---

## 5. `project_id` Now Required for Task Creation

Creating a task now requires a `project_id`. Omitting it returns HTTP 422 Unprocessable Entity.

**Before (v1):**
```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

You'll need to either:
- Require users to specify a project when creating tasks
- Default to a pre-existing project ID
- Create a project first (via the new `/v2/projects` endpoint)

---

## 6. List Endpoints Return Paginated Envelope

List endpoints no longer return a bare array. They return an envelope with pagination metadata.

**Before (v1):**
```json
GET /tasks

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```json
GET /v2/tasks

{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To iterate all results, pass `?cursor=<next_cursor>` for subsequent pages. When `next_cursor` is `null`, you've reached the end.

**Before (v1):**
```javascript
const tasks = await fetch('/tasks').then(r => r.json());
// tasks is an array
tasks.forEach(task => console.log(task.title));
```

**After (v2):**
```javascript
let allTasks = [];
let cursor = null;

do {
  const url = cursor ? `/v2/tasks?cursor=${cursor}` : '/v2/tasks';
  const response = await fetch(url, {
    headers: { 'Authorization': 'Bearer your_api_token' }
  }).then(r => r.json());

  allTasks.push(...response.items);
  cursor = response.next_cursor;
} while (cursor);

allTasks.forEach(task => console.log(task.title));
```

---

## Migration Checklist

Follow these steps to migrate your application:

- [ ] **Update base URL** — add `/v2/` prefix to all task endpoint paths
- [ ] **Update authentication** — replace `X-Auth-Token` with `Authorization: Bearer`
- [ ] **Update ID handling** — change from integer to UUID string type
- [ ] **Rename field references** — replace `done` with `completed` in all code
- [ ] **Add project requirement** — ensure `project_id` is provided when creating tasks
- [ ] **Update list response handling** — parse `items` array from envelope instead of bare array
- [ ] **Implement pagination** — use `next_cursor` for iterating beyond first page (optional, but recommended)
- [ ] **Run tests** — verify all integration tests pass with v2 endpoints
- [ ] **Update documentation** — reflect new field names and response formats

---

## Upgrade Command

```bash
zrb upgrade --api-version 2
```

This command updates your project configuration to use v2 endpoints. Manual code changes are still required for the breaking changes listed above.