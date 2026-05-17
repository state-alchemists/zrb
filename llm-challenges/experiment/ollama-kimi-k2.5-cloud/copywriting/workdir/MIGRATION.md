# Zrb CLI v1 to v2 Migration Guide

This guide covers every breaking change when migrating from Zrb CLI v1 to v2. Review each section and update your code accordingly.

---

## Breaking Change 1: API Version Prefix

All endpoints now require the `/v2/` prefix.

**Before (v1):**
```http
GET /tasks
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**
```http
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Breaking Change 2: Authentication Header

The authentication header has changed from `X-Auth-Token` to `Authorization: Bearer`.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

Requests using the old `X-Auth-Token` header will receive HTTP 401.

---

## Breaking Change 3: Task ID Type Changed to UUID

Task IDs are now UUID strings instead of integers. This affects all endpoints that reference a task by ID.

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

Update any code that assumes `id` is an integer.

---

## Breaking Change 4: Field Renamed: `done` → `completed`

The task status field has been renamed from `done` to `completed`.

**Before (v1):**
```json
// Request body
{
  "title": "Updated title",
  "done": true
}

// Response
{
  "id": 42,
  "title": "Updated title",
  "done": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2):**
```json
// Request body
{
  "title": "Updated title",
  "completed": true
}

// Response
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Updated title",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Breaking Change 5: Task Creation Requires `project_id`

Creating a task now requires a `project_id` field. Requests without it will return HTTP 422.

**Before (v1):**
```http
POST /tasks

{
  "title": "New task title"
}
```

**After (v2):**
```http
POST /v2/tasks

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

## Breaking Change 6: List Endpoints Return Paginated Envelope

The `GET /tasks` endpoint no longer returns a bare array. It now returns a paginated envelope.

**Before (v1):**
```http
GET /tasks

// Response
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```http
GET /v2/tasks

// Response
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b3c4...", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, pass the cursor as a query parameter:
```http
GET /v2/tasks?cursor=cursor_xyz
```

---

## Migration Checklist

Use this checklist to ensure your migration is complete:

- [ ] Update base URL to include `/v2/` prefix for all endpoints
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] Update type definitions: task `id` is now a string (UUID), not an integer
- [ ] Rename all references from `done` to `completed` in request bodies and response handling
- [ ] Update task creation logic to include required `project_id` field
- [ ] Update list tasks response handling to parse the paginated envelope (`items`, `total`, `next_cursor`)
- [ ] Implement cursor-based pagination if iterating through all tasks
- [ ] Update tests to use UUID strings instead of integer IDs
- [ ] Verify error handling for HTTP 401 (auth) and HTTP 422 (missing `project_id`)

---

## Upgrade Command

Install the latest v2 release:

```bash
zrb upgrade --to=v2
```
