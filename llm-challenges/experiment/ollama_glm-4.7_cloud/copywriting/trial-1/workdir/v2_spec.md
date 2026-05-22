# Zrb Task API — v2 Reference

## What's New in v2

v2 introduces projects, improved pagination, and stricter auth. Several v1 fields and conventions have changed.

## Breaking Changes Summary

1. All endpoints are now prefixed with `/v2/`
2. Authentication header changed
3. Task `id` type changed from integer to UUID string
4. Task field `done` renamed to `completed`
5. Task creation now requires `project_id`
6. List endpoints return a paginated envelope instead of a bare array

---

## Authentication

Header changed from `X-Auth-Token` to Bearer token:

```
Authorization: Bearer <your_api_token>
```

Requests with `X-Auth-Token` will receive HTTP 401.

## Data Types

### Task Object (v2)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

- `id` — UUID string (was integer in v1)
- `title` — string (unchanged)
- `completed` — boolean (renamed from `done`)
- `project_id` — string, required (new field)
- `created_at` — ISO 8601 timestamp (unchanged)

### Paginated List Envelope

All list endpoints now return:

```json
{
  "items": [...],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Pass `?cursor=<next_cursor>` to fetch the next page.

## Endpoints

### List Tasks

`GET /v2/tasks`

**Query params:**
- `cursor` — pagination cursor (optional)
- `limit` — max results per page, default 20

**Response:** paginated envelope (see above).

### Get Task

`GET /v2/tasks/{id}`

`id` is now a UUID string.

### Create Task

`POST /v2/tasks`

**Request body:**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

`project_id` is now **required**. Omitting it returns HTTP 422.

**Response:** the created task object (HTTP 201).

### Update Task

`PUT /v2/tasks/{id}`

**Request body** (all fields optional):
```json
{
  "title": "Updated title",
  "completed": true
}
```

Note: field is `completed`, not `done`.

### Delete Task

`DELETE /v2/tasks/{id}`

**Response:** HTTP 204 No Content.
