# Zrb CLI Migration Guide: v1 to v2

This guide covers every breaking change in Zrb CLI v2 and how to update your code. If you're already running v1 integrations, work through each section in order.

---

## Overview of Breaking Changes

| # | Change | Section |
|---|--------|---------|
| 1 | All endpoints moved to `/v2/` prefix | [Endpoint Prefixes](#1-endpoint-prefixes) |
| 2 | Auth header changed from `X-Auth-Token` to Bearer token | [Authentication](#2-authentication) |
| 3 | Task `id` changed from integer to UUID string | [Task ID Type](#3-task-id-type) |
| 4 | Task field `done` renamed to `completed` | [Field Rename](#4-field-rename-done--completed) |
| 5 | Task creation now requires `project_id` | [Required project_id](#5-required-project_id) |
| 6 | List endpoints return paginated envelope instead of bare array | [Pagination Envelope](#6-pagination-envelope) |

---

## 1. Endpoint Prefixes

All endpoints are now under `/v2/`. Requests to `/tasks` will return `404`.

**Before (v1)**
```
GET /tasks
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2)**
```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

## 2. Authentication

The `X-Auth-Token` header is no longer accepted. Switch to Bearer token authentication.

**Before (v1)**
```http
X-Auth-Token: your_api_key_here
```

**After (v2)**
```http
Authorization: Bearer your_api_token_here
```

Requests with `X-Auth-Token` will receive `401 Unauthorized`.

---

## 3. Task ID Type

Task IDs are now UUID strings instead of integers. Update any code that parses or stores task IDs as integers.

**Before (v1)**
```json
{ "id": 42 }
```

**After (v2)**
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
```

Check code that references task IDs — type annotations, database columns, URL parameters, and cache keys may need updating.

---

## 4. Field Rename: `done` → `completed`

The `done` boolean field is renamed to `completed` in all task objects and request bodies.

**Before (v1) — task object**
```json
{ "id": 1, "title": "Write tests", "done": true }
```

**After (v2) — task object**
```json
{ "id": "a1b2c3d4-...", "title": "Write tests", "completed": true }
```

**Before (v1) — update request**
```json
{ "done": true }
```

**After (v2) — update request**
```json
{ "completed": true }
```

---

## 5. Required `project_id`

Create Task now requires a `project_id` field. Omitting it returns `422 Unprocessable Entity`.

**Before (v1) — create task**
```json
{ "title": "New task title" }
```

**After (v2) — create task**
```json
{ "title": "New task title", "project_id": "proj_abc123" }
```

Fetch or create a project before creating tasks if you don't already have one. Update your task creation logic to include `project_id`.

---

## 6. Pagination Envelope

List endpoints no longer return a bare array. They return a wrapper envelope with `items`, `total`, and `next_cursor`.

**Before (v1) — list tasks response**
```json
[
  { "id": 1, "title": "Buy milk", "done": false },
  { "id": 2, "title": "Ship v1", "done": true }
]
```

**After (v2) — list tasks response**
```json
{
  "items": [
    { "id": "...", "title": "Buy milk", "completed": false },
    { "id": "...", "title": "Ship v1", "completed": true }
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

Access tasks via `response.items` instead of `response` directly. Use `next_cursor` with a `?cursor=` query param to paginate.

---

## Migration Checklist

Work through these steps in order:

- [ ] Update all endpoint URLs to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] Update task ID handling — convert integer assumptions to UUID string handling
- [ ] Rename `done` to `completed` in task objects, request bodies, and response parsing
- [ ] Add `project_id` to task creation requests (fetch or create a project first if needed)
- [ ] Update list response parsing — access `items` array from envelope, use `next_cursor` for pagination
- [ ] Run your integration tests against the v2 endpoint to verify behavior

---

## Upgrade Command

```bash
npm install zrb@latest
```

Or if you're using the CLI directly:

```bash
brew upgrade zrb
```