# Zrb CLI v1 to v2 Migration Guide

This guide covers every breaking change when upgrading from Zrb CLI v1 to v2 and shows you exactly how to update your code.

** TL;DR:**
- Request URLs now require a `/v2/` prefix
- Auth header changed to `Authorization: Bearer <token>`
- Task `id` is a UUID string, not an integer
- Task field `done` is now `completed`
- Creating a task requires a `project_id`
- List endpoints return a paginated envelope instead of a bare array

---

## Breaking Changes

### 1. API Version Prefix Required

All endpoints must now include `/v2/` in the request path. Unprefixed requests return `404`.

**Before (v1):**
```bash
curl https://api.example.com/tasks
curl https://api.example.com/tasks/42
```

**After (v2):**
```bash
curl https://api.example.com/v2/tasks
curl https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication Header Changed

The `X-Auth-Token` header is no longer accepted. Use an `Authorization` Bearer token instead. Requests sent with `X-Auth-Token` will receive `401 Unauthorized`.

**Before (v1):**
```bash
curl -H "X-Auth-Token: my_api_key" \
  https://api.example.com/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer my_api_token" \
  https://api.example.com/v2/tasks
```

---

### 3. Task `id` Changed from Integer to UUID String

Task identifiers are no longer integers. They are now UUID strings. Update any code that assumes `id` is numeric or performs arithmetic on it.

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

---

### 4. Task Field `done` Renamed to `completed`

The boolean status field on task objects is now named `completed`. Update all serialisation, deserialisation, and filter logic.

**Before (v1):**
```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2):**
```json
{
  "title": "Updated title",
  "completed": true
}
```

---

### 5. Task Creation Now Requires `project_id`

Creating a task without a `project_id` returns `422 Unprocessable Entity`.

**Before (v1):**
```bash
curl -X POST https://api.example.com/tasks \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: my_api_key" \
  -d '{"title": "New task title"}'
```

**After (v2):**
```bash
curl -X POST https://api.example.com/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my_api_token" \
  -d '{"title": "New task title", "project_id": "proj_abc123"}'
```

---

### 6. List Endpoints Return a Paginated Envelope

`GET /v2/tasks` no longer returns a bare array. It returns a paginated envelope containing `items`, `total`, and `next_cursor`.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": null
}
```

To fetch subsequent pages, pass the `next_cursor` value as the `?cursor=` query parameter:

```bash
curl "https://api.example.com/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer my_api_token"
```

---

## Migration Checklist

Use this checklist to verify your upgrade:

- [ ] Add `/v2/` prefix to all endpoint URLs (`/tasks` -> `/v2/tasks`)
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] Update task `id` handling from integer to UUID string
- [ ] Rename all references from `done` to `completed` in request/response payloads
- [ ] Start including `project_id` in every `POST /v2/tasks` request
- [ ] Update list-endpoint consumers to read `response.items` instead of the root array
- [ ] Add cursor-based pagination support where you iterate over list results
- [ ] Regenerate types, fixtures, and mocks with the new field names and shapes
- [ ] Run integration tests against v2 and confirm all `2xx` responses

---

## Upgrade Command

Install the latest v2 CLI globally via npm:

```bash
npm install -g zrb-cli@latest
```

Verify the installation:

```bash
zrb --version
# Expected: 2.x.x or higher
```
