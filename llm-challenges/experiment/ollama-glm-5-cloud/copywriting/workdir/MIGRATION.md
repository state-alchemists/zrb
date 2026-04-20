# Zrb CLI v1 → v2 Migration Guide

This guide covers all breaking changes when upgrading from Zrb CLI v1 to v2.

## Breaking Changes Overview

| Change | v1 | v2 |
|--------|----|----|
| API prefix | `/tasks` | `/v2/tasks` |
| Auth header | `X-Auth-Token` | `Authorization: Bearer` |
| Task ID type | Integer | UUID string |
| Status field | `done` | `completed` |
| Required field | — | `project_id` (create) |
| List response | Bare array | Paginated envelope |

---

## 1. API Endpoint Prefix

All endpoints now require the `/v2/` prefix.

**Before (v1):**
```bash
curl https://api.zrb.dev/tasks
curl https://api.zrb.dev/tasks/42
curl -X POST https://api.zrb.dev/tasks
```

**After (v2):**
```bash
curl https://api.zrb.dev/v2/tasks
curl https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl -X POST https://api.zrb.dev/v2/tasks
```

---

## 2. Authentication Header

The authentication header has changed from a custom header to standard Bearer token authentication.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.dev/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.dev/v2/tasks
```

> ⚠️ **Note:** Requests using `X-Auth-Token` will receive HTTP 401 Unauthorized.

---

## 3. Task ID Type Changed

Task IDs have changed from integers to UUID strings.

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
  "completed": false
}
```

**Impact:**
- Update any code that stores or compares `id` as an integer
- URL paths now use UUIDs: `/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890`

---

## 4. Field Rename: `done` → `completed`

The task status field has been renamed.

**Before (v1):**
```json
{
  "title": "Ship v2",
  "done": true
}
```

**After (v2):**
```json
{
  "title": "Ship v2",
  "completed": true
}
```

**Impact:**
- Update all request bodies and response parsers
- Update any field validation or type definitions

---

## 5. Required `project_id` for Task Creation

Creating a task now requires a `project_id`.

**Before (v1):**
```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your_api_key" \
  -d '{"title": "New task"}'
```

**After (v2):**
```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_token" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

> ⚠️ **Note:** Omitting `project_id` returns HTTP 422 Unprocessable Entity.

---

## 6. List Response Format Changed

List endpoints now return a paginated envelope instead of a bare array.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc"},
    {"id": "b2c3...", "title": "Ship v1", "completed": true, "project_id": "proj_abc"}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Impact:**
- Access tasks via `response.items` instead of iterating the response directly
- Pagination is now built-in; use `?cursor=<next_cursor>` for subsequent pages
- The `total` field provides the overall count

**Before (v1) — Iterate all tasks:**
```javascript
const tasks = await fetch('/tasks').then(r => r.json());
tasks.forEach(task => console.log(task.title));
```

**After (v2) — Iterate all tasks:**
```javascript
const response = await fetch('/v2/tasks').then(r => r.json());
response.items.forEach(task => console.log(task.title));
console.log(`Total: ${response.total}`);
```

---

## Migration Checklist

Before deploying to production, verify each item:

- [ ] **Update API base URL** — Add `/v2` prefix to all endpoints
- [ ] **Switch auth header** — Replace `X-Auth-Token` with `Authorization: Bearer`
- [ ] **Update ID handling** — Change `id` type from integer to string (UUID)
- [ ] **Rename status field** — Replace `done` with `completed` everywhere
- [ ] **Add `project_id`** — Include required `project_id` in all task creation requests
- [ ] **Update list response handling** — Access `response.items` instead of raw array
- [ ] **Add pagination logic** — Handle `next_cursor` for large result sets
- [ ] **Update tests** — Adjust all fixtures, mocks, and assertions for new types
- [ ] **Run integration tests** — Verify end-to-end flow against v2 sandbox

---

## Upgrade Command

```bash
zrb upgrade --version 2
```

This command updates your local configuration and outputs a diff of changes to review.