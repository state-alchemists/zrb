# Migrating from Zrb v1 to v2

Zrb v2 introduces projects, cursor-based pagination, and stricter authentication. Because several core conventions have changed, upgrading requires explicit code changes beyond a simple package update.

This guide lists every breaking change and shows the exact before-and-after code you need to write.

## Breaking Changes

### 1. All endpoints are now prefixed with `/v2/`

v1 routes lived at the root path. v2 moves every endpoint under `/v2/`.

**Before (v1)**

```bash
curl -H "X-Auth-Token: $API_KEY" \
  https://api.zrb.io/tasks
```

**After (v2)**

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  https://api.zrb.io/v2/tasks
```

### 2. Authentication header changed from `X-Auth-Token` to Bearer token

The custom `X-Auth-Token` header is removed. Requests that still send it will receive HTTP `401 Unauthorized`.

**Before (v1)**

```bash
curl -H "X-Auth-Token: abc123" \
  https://api.zrb.io/tasks
```

**After (v2)**

```bash
curl -H "Authorization: Bearer abc123" \
  https://api.zrb.io/v2/tasks
```

### 3. Task `id` changed from integer to UUID string

IDs are no longer auto-incrementing integers. Every task now has a UUID string identifier. Update any client-side storage, caching, or type definitions that assumed an integer.

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

### 4. Task field `done` renamed to `completed`

The boolean flag is now named `completed`. Update both response parsing and request payloads.

**Before (v1)**

```json
{
  "done": true
}
```

**After (v2)**

```json
{
  "completed": true
}
```

### 5. Task creation now requires `project_id`

Creating a task without a `project_id` returns HTTP `422 Unprocessable Entity`.

**Before (v1)**

```bash
curl -X POST https://api.zrb.io/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "New task title"}'
```

**After (v2)**

```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{"title": "New task title", "project_id": "proj_abc123"}'
```

### 6. List endpoints return a paginated envelope instead of a bare array

`GET /v2/tasks` no longer returns a top-level JSON array. It returns an object containing `items`, `total`, and `next_cursor`. Pass `?cursor=<next_cursor>` to paginate forward.

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
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "b3c4...", "title": "Ship v2", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

---

## Step-by-Step Migration Checklist

1. Update the Zrb CLI to the latest v2 version.
2. Replace the base URL or prepend `/v2/` to every endpoint path.
3. Swap `X-Auth-Token` for `Authorization: Bearer <token>` in all requests.
4. Update your Task model or type definition:
   - Change `id` from `number` (or `int`) to `string` (UUID).
   - Rename the `done` field to `completed`.
   - Add the required `project_id` field.
5. Update task-creation logic to always include `project_id`.
6. Update list-tasks response handling to read `response.items` instead of the raw array.
7. Implement cursor-based pagination using `next_cursor` and the `?cursor=` query parameter.
8. Run integration tests against the v2 endpoints.

## Upgrade Command

```bash
npm install -g zrb@latest
```
