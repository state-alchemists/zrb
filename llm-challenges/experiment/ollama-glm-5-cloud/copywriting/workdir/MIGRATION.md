# Zrb Task API v1 → v2 Migration Guide

v2 introduces projects, pagination, and stricter authentication. This guide covers all breaking changes and migration steps for existing v1 integrations.

---

## Breaking Changes Overview

| Change | v1 | v2 |
|--------|----|----|
| Authentication header | `X-Auth-Token` | `Authorization: Bearer` |
| Endpoint prefix | `/tasks` | `/v2/tasks` |
| Task `id` type | integer | UUID string |
| Task status field | `done` | `completed` |
| Task creation | `title` only | `title` + `project_id` (required) |
| List response | bare array | paginated envelope |

---

## Authentication Header Change

**Breaking:** Requests using `X-Auth-Token` will receive HTTP 401.

### v1

```http
GET /tasks HTTP/1.1
X-Auth-Token: your_api_key
```

### v2

```http
GET /v2/tasks HTTP/1.1
Authorization: Bearer your_api_token
```

**Migration:** Update your HTTP client to send the Bearer token in the `Authorization` header instead of `X-Auth-Token`.

---

## Endpoint Prefix

**Breaking:** All v1 endpoints return HTTP 404 on v2 servers.

### v1

```
GET /tasks
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

### v2

```
GET /v2/tasks
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

**Migration:** Prepend `/v2` to all endpoint paths in your client configuration or base URL.

---

## Task ID Type Change

**Breaking:** Integer IDs are no longer accepted. UUID strings are required for all task operations.

### v1

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

### v2

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123"
}
```

**Migration:**
- Update all ID type annotations from `int` to `string` in typed languages.
- If you store task IDs in a database, migrate the column type to `VARCHAR(36)` or equivalent.
- Update any ID validation logic to accept UUID format.

---

## Field Rename: `done` → `completed`

**Breaking:** The `done` field no longer exists in responses. The `completed` field replaces it.

### v1

```json
{
  "id": 42,
  "title": "Write tests",
  "done": true
}
```

### v2

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true
}
```

### Update Request (v1)

```json
{
  "title": "Updated title",
  "done": true
}
```

### Update Request (v2)

```json
{
  "title": "Updated title",
  "completed": true
}
```

**Migration:**
- Update all struct definitions, serializers, and deserializers to use `completed`.
- Refactor any client-side logic referencing `task.done` to use `task.completed`.

---

## Required `project_id` on Task Creation

**Breaking:** Creating a task without `project_id` returns HTTP 422.

### v1

```json
POST /tasks
{
  "title": "New task title"
}
```

### v2

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Migration:**
- Identify all task creation calls in your codebase.
- Ensure `project_id` is provided for every new task.
- If your application doesn't have a project concept, create a default project via the v2 projects API and use its ID.

---

## List Response Format Change

**Breaking:** List endpoints no longer return a bare array. Direct iteration over the response will fail.

### v1

```json
GET /tasks

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### v2

```json
GET /v2/tasks

{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Pagination:** Pass `?cursor=<next_cursor>` to fetch the next page. Use `?limit=N` to control page size (default: 20).

**Migration:**
- Update response parsing to extract `items` from the envelope.
- If you need all results, implement cursor-based pagination:
  ```pseudo
  tasks = []
  cursor = null
  do {
    response = GET /v2/tasks?cursor={cursor}
    tasks.extend(response.items)
    cursor = response.next_cursor
  } while (cursor != null)
  ```
- Update any count logic to use `total` from the envelope instead of array length.

---

## Migration Checklist

- [ ] Update authentication: change `X-Auth-Token` to `Authorization: Bearer`
- [ ] Update base URL or endpoint paths to include `/v2` prefix
- [ ] Change task ID type from `int` to `string` (UUID)
- [ ] Rename `done` to `completed` in all structs, models, and logic
- [ ] Add `project_id` to all task creation requests
- [ ] Update list response handling: extract `items` from envelope
- [ ] Implement cursor-based pagination if fetching all results
- [ ] Update tests to use new endpoint paths and data shapes
- [ ] Run integration tests against v2 staging environment

---

## Upgrade

```bash
zrb upgrade --version 2
```

This updates your CLI to v2. API changes require client code updates per the checklist above.