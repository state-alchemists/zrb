# Zrb CLI v1 to v2 Migration Guide

Zrb v2 introduces projects, pagination, and stricter authentication. This guide covers every breaking change and provides code examples to help you migrate your existing code.

---

## Breaking Changes

### 1. Base URL Prefix Required

All endpoints are now prefixed with `/v2/`.

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

The `X-Auth-Token` header is no longer supported. Use Bearer token format instead.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.io/tasks
```

```javascript
// JavaScript
fetch('/tasks', {
  headers: { 'X-Auth-Token': apiKey }
});
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.io/v2/tasks
```

```javascript
// JavaScript
fetch('/v2/tasks', {
  headers: { 'Authorization': `Bearer ${apiToken}` }
});
```

> **Note:** Requests with the old `X-Auth-Token` header will receive HTTP 401.

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
// JavaScript - old integer IDs
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
// JavaScript - new UUID strings
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
fetch(`/v2/tasks/${taskId}`);
```

> **Impact:** Update any code that treats task IDs as numbers or relies on sequential ID ordering.

---

### 4. Field Rename: `done` → `completed`

The task status field has been renamed from `done` to `completed`.

**Before (v1):**
```json
{
  "id": 1,
  "title": "Buy milk",
  "done": false
}
```

```javascript
// Creating a task
fetch('/tasks', {
  method: 'POST',
  body: JSON.stringify({ title: 'New task', done: false })
});

// Checking task status
if (task.done) { ... }
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Buy milk",
  "completed": false
}
```

```javascript
// Updating a task
fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  body: JSON.stringify({ completed: true })
});

// Checking task status
if (task.completed) { ... }
```

> **Impact:** Update all references to `done` in request bodies, responses, and conditional logic.

---

### 5. Task Creation Requires `project_id`

Tasks must now belong to a project. The `project_id` field is required when creating tasks.

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
  headers: { 'Content-Type': 'application/json' },
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

> **Note:** Omitting `project_id` will return HTTP 422.

---

### 6. List Endpoints Return Paginated Envelope

List endpoints no longer return bare arrays. They now return a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

```javascript
// Old approach - direct array
fetch('/tasks')
  .then(res => res.json())
  .then(tasks => {
    tasks.forEach(task => console.log(task.title));
  });
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false},
    {"id": "b2c3d4e5-...", "title": "Ship v2", "completed": true}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// New approach - paginated envelope
fetch('/v2/tasks')
  .then(res => res.json())
  .then(data => {
    data.items.forEach(task => console.log(task.title));
    if (data.next_cursor) {
      // Fetch next page: /v2/tasks?cursor=cursor_xyz
    }
  });
```

**Pagination via cursor:**
```bash
# Fetch first page
curl "https://api.zrb.io/v2/tasks?limit=20"

# Fetch next page using cursor from previous response
curl "https://api.zrb.io/v2/tasks?cursor=cursor_xyz&limit=20"
```

> **Impact:** Update all list handling code to access `response.items` instead of the response directly.

---

## Migration Checklist

Use this checklist to ensure a complete migration:

- [ ] **Update base URLs** — Add `/v2/` prefix to all endpoint paths
- [ ] **Replace authentication header** — Change `X-Auth-Token` to `Authorization: Bearer <token>`
- [ ] **Update ID handling** — Treat task IDs as strings (UUIDs), not integers
- [ ] **Rename field references** — Replace all `done` with `completed` in request/response handling
- [ ] **Add project_id to task creation** — Ensure all `POST /v2/tasks` requests include `project_id`
- [ ] **Update list response parsing** — Access tasks via `response.items` instead of response directly
- [ ] **Handle pagination** — Implement cursor-based pagination if you fetch more than one page of results
- [ ] **Update tests** — Adjust test fixtures and assertions to match new data types and response shapes
- [ ] **Update documentation** — Refresh any API client documentation or SDKs

---

## Upgrade Command

Install the latest v2 CLI:

```bash
npm install -g @zrb/cli@latest
```

Or update your `package.json`:

```json
{
  "dependencies": {
    "@zrb/cli": "^2.0.0"
  }
}
```

Then run:

```bash
npm install
```

---

## Quick Reference: v1 vs v2 Side-by-Side

| Aspect | v1 | v2 |
|--------|----|----|
| Base path | `/tasks` | `/v2/tasks` |
| Auth header | `X-Auth-Token: <key>` | `Authorization: Bearer <token>` |
| Task ID type | Integer (`42`) | UUID string (`"a1b2c3d4-..."`) |
| Status field | `done` | `completed` |
| Required for creation | `title` | `title`, `project_id` |
| List response | Array `[]` | Envelope `{items, total, next_cursor}` |

---

*Need help? Open an issue at https://github.com/zrb-io/zrb/issues*
