# Zrb CLI v1 to v2 Migration Guide

This guide explains how to migrate from Zrb CLI v1 to v2. The v2 release introduces breaking changes around authentication, task identification, project scoping, and pagination. This guide covers each breaking change with before/after code examples.

---

## Breaking Changes Overview

| Change | v1 | v2 |
|--------|----|----|
| Endpoint prefix | `/tasks` | `/v2/tasks` |
| Authentication | `X-Auth-Token: <key>` | `Authorization: Bearer <token>` |
| Task ID type | Integer | UUID string |
| Completion status field | `done` | `completed` |
| Project scoping | Optional | Required for creation |
| List response format | Bare array | Paginated envelope |

---

## 1. Authentication Header

### Change

Authentication header changed from `X-Auth-Token` to Bearer token format. Requests with `X-Auth-Token` will receive HTTP 401.

### Migration

**v1 (before):**
```bash
curl -X GET "https://api.zrb.app/tasks" \
  -H "X-Auth-Token: your_api_key"
```

**v2 (after):**
```bash
curl -X GET "https://api.zrb.app/v2/tasks" \
  -H "Authorization: Bearer your_api_token"
```

---

## 2. Endpoint Prefix

### Change

All endpoints are now prefixed with `/v2/`. The old routes at `/tasks` no longer exist.

### Migration

**v1 (before):**
```bash
curl -X POST "https://api.zrb.app/tasks"
```

**v2 (after):**
```bash
curl -X POST "https://api.zrb.app/v2/tasks"
```

---

## 3. Task ID Type

### Change

Task `id` changed from integer to UUID string (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

### Migration

**v1 (before):**
```javascript
const task = await zrb.tasks.get(42);
console.log(task.id); // 42 (number)
```

**v2 (after):**
```javascript
const task = await zrb.tasks.get("a1b2c3d4-e5f6-7890-abcd-ef1234567890");
console.log(task.id); // "a1b2c3d4-e5f6-7890-abcd-ef1234567890" (string)
```

---

## 4. Task Fields: `done` → `completed`

### Change

The `done` field was renamed to `completed`. Using `done` in v2 requests will be ignored or may cause validation errors.

### Migration

**v1 (before):**
```json
{
  "title": "Write tests",
  "done": true
}
```

**v2 (after):**
```json
{
  "title": "Write tests",
  "completed": true
}
```

---

## 5. Project Scoping

### Change

Task creation now requires `project_id`. Omitting it returns HTTP 422 (Validation Error).

### Migration

**v1 (before):**
```bash
curl -X POST "https://api.zrb.app/tasks" \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

**v2 (after):**
```bash
curl -X POST "https://api.zrb.app/v2/tasks" \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

---

## 6. Pagination

### Change

List endpoints return a paginated envelope instead of a bare array. The response now includes `items`, `total`, and `next_cursor` fields.

### Migration

**v1 (before):**
```javascript
const tasks = await zrb.tasks.list();
// tasks is an array: [{...}, {...}]
```

**v2 (after):**
```javascript
const response = await zrb.tasks.list();
// response is an object: { items: [...], total: 42, next_cursor: "cursor_xyz" }
const tasks = response.items;

// For pagination:
const nextResponse = await zrb.tasks.list({ cursor: response.next_cursor, limit: 20 });
```

---

## Migration Checklist

- [ ] **Update endpoint URLs**: Replace all `/tasks` paths with `/v2/tasks`
- [ ] **Update authentication**: Change `X-Auth-Token` header to `Authorization: Bearer <token>`
- [ ] **Update task ID handling**: Convert integer IDs to UUID strings throughout your codebase
- [ ] **Rename fields**: Replace all `done` with `completed` in request/response payloads
- [ ] **Add project_id**: Include `project_id` in all `POST /v2/tasks` requests
- [ ] **Handle paginated responses**: Update your list handling to extract `items` from the envelope
- [ ] **Update error handling**: Expect HTTP 422 for missing `project_id` instead of silent defaults
- [ ] **Review SDK/client libraries**: Update any custom HTTP wrappers or SDK integrations
- [ ] **Test against v2**: Run end-to-end tests with the new endpoint and data format
- [ ] **Update docs**: Refresh any internal documentation or comments referencing v1

---

## Upgrade Command

Once you've completed the code changes above, deploy your updated code. No server-side migration is required — the v2 API is compatible with existing v1 data, but your clients must be updated to the new format.

```bash
# Example: Verify your migration by testing the list endpoint
curl -X GET "https://api.zrb.app/v2/tasks?limit=5" \
  -H "Authorization: Bearer your_token"
```
