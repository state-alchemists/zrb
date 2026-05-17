# Zrb CLI v1 → v2 Migration Guide

Zrb v2 introduces projects, cursor-based pagination, and stricter authentication. This guide details every breaking change and shows how to update your code.

## Overview of Breaking Changes

| Change | Impact |
|--------|--------|
| Base URL prefix moved to `/v2/` | All endpoint URLs must be updated |
| Header-based auth replaced with Bearer tokens | Auth headers must be renamed and reformatted |
| Task `id` changed from integer to UUID string | Storage, comparisons, and URL formatting must handle strings |
| Task field `done` renamed to `completed` | Serialization and filtering logic must be updated |
| `project_id` is now required on task creation | All create calls must supply a project identifier |
| List endpoints return a paginated envelope | Response parsing must account for the new wrapper shape |

---

## 1. Endpoint Prefix Changed

All paths must now begin with `/v2/`.

**Before (v1):**

```bash
curl https://api.zrb.example/tasks
curl https://api.zrb.example/tasks/42
```

**After (v2):**

```bash
curl https://api.zrb.example/v2/tasks
curl https://api.zrb.example/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication Header Changed

The `X-Auth-Token` header is removed. Use `Authorization: Bearer <token>` instead. Requests with the old header now return HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: my_api_key" \
  https://api.zrb.example/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer my_api_token" \
  https://api.zrb.example/v2/tasks
```

---

## 3. Task `id` Changed from Integer to UUID

Task identifiers are now UUID strings. Do not assume an integer type; update any parsing, storage, or arithmetic logic that relied on numeric IDs.

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

## 4. Task Field `done` Renamed to `completed`

The boolean field indicating task completion is now named `completed`. Using `done` in request bodies or expecting it in responses will fail.

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

## 5. `project_id` Is Now Required on Creation

Creating a task without a `project_id` returns HTTP 422. Provide a valid project identifier in every create request.

**Before (v1):**

```bash
curl -X POST https://api.zrb.example/tasks \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: my_api_key" \
  -d '{"title": "New task"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.example/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my_api_token" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

---

## 6. List Endpoints Return a Paginated Envelope

`GET /v2/tasks` no longer returns a bare array. It returns an envelope containing `items`, `total`, and `next_cursor`. Traverse pages by passing the cursor in the `?cursor` query parameter.

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
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Paginated request example:

```bash
curl "https://api.zrb.example/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer my_api_token"
```

---

## Migration Checklist

Use this checklist to verify every integration point in your codebase.

- [ ] Update base URL paths to include the `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] Change `id` handling from integer to UUID string (no arithmetic, string storage)
- [ ] Rename all references from `done` to `completed` in requests and response parsing
- [ ] Add a valid `project_id` to every task creation payload
- [ ] Update list-endpoint consumers to unwrap `items` from the paginated envelope
- [ ] Add pagination logic to consume `next_cursor` when iterating through all tasks
- [ ] Run integration tests against the v2 endpoints
- [ ] Update internal documentation and client libraries

---

## Upgrade Command

Install the latest CLI version globally:

```bash
npm install -g zrb@latest
```

Verify the installation:

```bash
zrb --version
```
