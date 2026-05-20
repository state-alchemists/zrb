# Zrb Task API: v1 → v2 Migration Guide

Zrb v2 introduces projects, paginated list endpoints, UUID-based task identifiers, and stricter authentication. This guide covers every breaking change and walks you through the migration.

## Overview of Changes

| Area | v1 | v2 |
|------|----|----|
| Base path | `/tasks` | `/v2/tasks` |
| Auth header | `X-Auth-Token` | `Authorization: Bearer` |
| Task ID type | Integer | UUID string |
| Task `done` field | `done` | `completed` |
| Task `project_id` | Not present | Required on create |
| List response | Bare array | Paginated envelope |
| Update request body | `"done": true` | `"completed": true` |

---

## Breaking Changes

### 1. Endpoint Prefix: `/v2/`

All endpoints are now prefixed with `/v2/`.

**Before (v1):**

```
GET /tasks
POST /tasks
GET /tasks/42
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**

```
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication: Bearer Token Replaces `X-Auth-Token`

The `X-Auth-Token` header is removed. Use a Bearer token via the `Authorization` header instead. Requests with `X-Auth-Token` receive HTTP 401.

**Before (v1):**

```
X-Auth-Token: sk-abc123
```

**After (v2):**

```
Authorization: Bearer zrb_abc123def456
```

---

### 3. Task ID: Integer → UUID String

Task IDs are now UUID strings. All endpoints that reference a task by ID must be updated.

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

Impacted endpoints: `GET /tasks/{id}`, `PUT /tasks/{id}`, `DELETE /tasks/{id}`.

If your application stores task IDs locally, the storage type must change from integer to string (UUID).

---

### 4. Field Rename: `done` → `completed`

The task field `done` is renamed to `completed` throughout the API — both in response bodies and request bodies.

**Before (v1) — response:**

```json
{
  "id": 42,
  "title": "Buy milk",
  "done": true,
  "created_at": "..."
}
```

**After (v2) — response:**

```json
{
  "id": "a1b2c3d4-...",
  "title": "Buy milk",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "..."
}
```

**Before (v1) — update request:**

```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2) — update request:**

```json
{
  "title": "Updated title",
  "completed": true
}
```

---

### 5. New Required Field: `project_id` on Create

Every task must belong to a project. The `project_id` field is now **required** when creating a task. Omitting it returns HTTP 422.

**Before (v1) — create request:**

```json
{
  "title": "Write tests"
}
```

**After (v2) — create request:**

```json
{
  "title": "Write tests",
  "project_id": "proj_abc123"
}
```

You must obtain or create a project before creating tasks. There is no default project — this decision is deliberate to enforce logical grouping from the start.

---

### 6. List Response: Bare Array → Paginated Envelope

The list endpoint no longer returns a bare array. Instead, it returns a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**

```json
[
  { "id": 1, "title": "Buy milk", "done": false, "created_at": "..." },
  { "id": 2, "title": "Ship v1", "done": true, "created_at": "..." }
]
```

**After (v2):**

```json
{
  "items": [
    { "id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..." },
    { "id": "c3d4...", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..." }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Access the task list via `response.items` instead of iterating the response directly.

To fetch the next page, pass the cursor as a query parameter:

```
GET /v2/tasks?cursor=cursor_xyz&limit=20
```

Optional query parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `cursor` | string | — | Pagination cursor from previous response |
| `limit` | integer | 20 | Max results per page |

---

### 7. Unchanged Behaviours

These remain the same in v2:

| Behaviour | v1 | v2 |
|-----------|----|----|
| Create response | HTTP 201 with task object | HTTP 201 with task object |
| Delete response | HTTP 204 No Content | HTTP 204 No Content |
| Not found | HTTP 404 | HTTP 404 |
| `title` field | string | string |
| `created_at` field | ISO 8601 timestamp | ISO 8601 timestamp |
| PUT fields all optional | Yes | Yes |

---

## Step-by-Step Migration Checklist

- [ ] **1. Update authentication.** Replace all `X-Auth-Token` headers with `Authorization: Bearer <token>`. Generate new v2 tokens if needed.
- [ ] **2. Prepend `/v2/` to all endpoint paths.** Every `/tasks` path becomes `/v2/tasks`.
- [ ] **3. Migrate task ID storage.** Change any integer-based task ID columns, variables, or cache keys to UUID strings (36 characters). Existing integer IDs cannot be used with v2 endpoints.
- [ ] **4. Rename `done` to `completed`.** Update all code that reads the `done` field from responses or sends `done` in request bodies.
- [ ] **5. Add `project_id` to task creation.** Determine your project ID and include it in every `POST /v2/tasks` request body. Create a project first if you don't have one.
- [ ] **6. Update list response handling.** Replace bare-array iteration with `response.items`. Add cursor-based pagination logic where you need more than one page.
- [ ] **7. Test against v2.** Run your integration tests against a v2 endpoint. Verify auth (401 on old header), create (422 without `project_id`), list (envelope shape), and update (`completed` field accepted).
- [ ] **8. Purge cached v1 data.** Clear any locally cached task lists or stale integer IDs to avoid type mismatches.

---

## Upgrade Command

Once your codebase is ready, install the latest version:

```bash
pip install --upgrade zrb
```

Verify the installed version:

```bash
zrb --version
# zrb 2.x.x
```
