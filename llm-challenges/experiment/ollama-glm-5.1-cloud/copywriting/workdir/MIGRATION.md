# Migrating from Zrb Task API v1 to v2

v2 introduces projects, cursor-based pagination, stricter authentication, and several field-level changes. This guide covers every breaking change with before/after examples so you can update your integration with minimal guesswork.

---

## Breaking Changes

### 1. Endpoint prefix

All endpoints are now prefixed with `/v2/`. Requests to the old paths will return 404.

**Before (v1)**

```
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2)**

```
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 2. Authentication header

The `X-Auth-Token` header is no longer accepted. Requests using it will receive HTTP 401.

**Before (v1)**

```http
GET /tasks HTTP/1.1
X-Auth-Token: abc123
```

**After (v2)**

```http
GET /v2/tasks HTTP/1.1
Authorization: Bearer abc123
```

### 3. Task `id` type changed from integer to UUID string

Task IDs are now UUIDs instead of auto-incrementing integers. Any code that parses, stores, or type-checks IDs as integers must be updated.

**Before (v1)**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2)**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 4. `done` renamed to `completed`

The boolean field `done` has been renamed to `completed`. Sending `done` in a request body will be silently ignored — the task will not be marked as completed.

**Before (v1)**

```json
{
  "title": "Ship v1",
  "done": true
}
```

**After (v2)**

```json
{
  "title": "Ship v1",
  "completed": true
}
```

### 5. `project_id` is now required when creating tasks

Task creation (`POST /v2/tasks`) requires a `project_id` field. Omitting it returns HTTP 422.

**Before (v1)**

```json
{
  "title": "New task title"
}
```

**After (v2)**

```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. List endpoints return a paginated envelope

`GET /v2/tasks` no longer returns a bare array. It returns an object with `items`, `total`, and `next_cursor`. Any code that iterates the response directly as an array must be updated to access `items`.

**Before (v1)**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2)**

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "e5f67890-...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, pass the cursor:

```
GET /v2/tasks?cursor=cursor_xyz
```

You can also set a custom page size with `limit` (default 20):

```
GET /v2/tasks?limit=50
```

---

## Migration Checklist

- [ ] Update all endpoint paths from `/tasks` to `/v2/tasks`
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer` header
- [ ] Update task ID handling: change from integer to UUID string (database columns, type annotations, serialization)
- [ ] Rename `done` to `completed` in all request bodies and response parsers
- [ ] Add `project_id` to every task creation request
- [ ] Update list endpoint consumers to read from the `items` array inside the paginated envelope instead of treating the response body as an array
- [ ] Implement cursor-based pagination if you need to retrieve more than one page of results
- [ ] Run your integration tests against the v2 API before switching production traffic

---

## Upgrade

```bash
zrb upgrade --target v2
```