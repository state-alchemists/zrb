# Zrb CLI v1 → v2 Migration Guide

This guide helps experienced Zrb v1 users migrate to v2. All changes are breaking — plan accordingly.

---

## Breaking Changes Summary

1. **API endpoint prefix**: `/tasks` → `/v2/tasks`
2. **Authentication header**: `X-Auth-Token` → `Authorization: Bearer <token>`
3. **Task ID type**: integer → UUID string
4. **Task field rename**: `done` → `completed`
5. **Create requirement**: `project_id` is now required
6. **List response format**: bare array → paginated envelope

---

## 1. Authentication Header

**v1:**
```bash
curl -H "X-Auth-Token: api_key_123" https://api.zrb.sh/tasks
```

**v2:**
```bash
curl -H "Authorization: Bearer api_key_123" https://api.zrb.sh/v2/tasks
```

> 💡 Requests using `X-Auth-Token` will receive HTTP 401.

---

## 2. Endpoint Path Prefix

All endpoints now require the `/v2/` prefix.

| Operation | v1 Path | v2 Path |
|-----------|---------|---------|
| List tasks | `GET /tasks` | `GET /v2/tasks` |
| Get task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create task | `POST /tasks` | `POST /v2/tasks` |
| Update task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

---

## 3. Task ID Type Change

v1 IDs were integers; v2 IDs are UUID strings.

**v1 response:**
```json
{"id": 42, "title": "Ship v1", "done": true, "created_at": "..."}
```

**v2 response:**
```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Ship v1", "completed": true, "created_at": "...", "project_id": "proj_abc"}
```

**Code impact example (JavaScript):**
```javascript
// v1
console.log(task.id + 1); // arithmetic works

// v2
console.log(task.id.toUpperCase()); // must treat as string, use string operations
```

---

## 4. `done` → `completed` Field Rename

The `done` boolean field has been renamed to `completed`.

**v1 request/response:**
```json
{"id": 42, "done": false}
```

**v2 request/response:**
```json
{"id": "uuid...", "completed": false, "project_id": "proj_x"}
```

> 💡 Using `done` in v2 update requests will be ignored. The field is strictly `completed`.

---

## 5. Required `project_id` on Creation

Creating a task now requires specifying `project_id`.

**v1 request (optional project):**
```json
{"title": "New task"}
```

**v2 request (required):**
```json
{
  "title": "New task",
  "project_id": "proj_abc123"
}
```

> 💡 Omitting `project_id` returns HTTP 422 Unprocessable Entity.

---

## 6. Paginated List Response

List endpoints return an envelope with `items`, `total`, and `next_cursor` — not a bare array.

**v1 response:**
```json
[
  {"id": 1, "title": "Task A", "done": false},
  {"id": 2, "title": "Task B", "done": true}
]
```

**v2 response:**
```json
{
  "items": [
    {"id": "uuid-a", "title": "Task A", "completed": false, "project_id": "proj_x"},
    {"id": "uuid-b", "title": "Task B", "completed": true, "project_id": "proj_y"}
  ],
  "total": 42,
  "next_cursor": "cursor_abc"
}
```

**Pagination example (v2):**
```bash
# First page
curl -H "Authorization: Bearer token" "https://api.zrb.sh/v2/tasks?limit=10"

# Next page (using cursor from response)
curl -H "Authorization: Bearer token" "https://api.zrb.sh/v2/tasks?cursor=cursor_abc&limit=10"
```

---

## Migration Checklist

Use this checklist to systematically migrate your codebase:

- [ ] **Update authentication**: replace all `X-Auth-Token` headers with `Authorization: Bearer <token>`
- [ ] **Add `/v2/` prefix**: update all endpoint paths (`/tasks` → `/v2/tasks`)
- [ ] **Handle ID type change**: update any code that assumes `task.id` is an integer; convert to string operations
- [ ] **Replace `done` with `completed`**: update all request bodies and response parsing for task objects
- [ ] **Supply `project_id`**: update task creation calls to include a valid `project_id`
- [ ] **Adapt list parsing**: refactor code that expects bare arrays — now you receive `{items: [], total: N, next_cursor: "..."}`; implement cursor-based pagination
- [ ] **Test pagination logic**: verify `next_cursor` handling with realistic data volumes
- [ ] **Update error handling**: expect HTTP 422 when `project_id` is missing during creation
- [ ] **Review SDK/client libraries**: ensure third-party clients are v2-compatible or write custom wrappers

---

## Final Step: Upgrade Command

Run the CLI upgrade command:

```bash
npm install -g @zrb/cli@latest
# or
brew upgrade zrb
# or
curl -sSL https://cli.zrb.sh/install.sh | sh
```

After upgrading, verify version:

```bash
zrb --version
# Expected: v2.x.x
```
