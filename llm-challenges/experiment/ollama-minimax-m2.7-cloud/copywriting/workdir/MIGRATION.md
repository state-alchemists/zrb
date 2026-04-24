# Zrb Task API v1 → v2 Migration Guide

This guide covers every breaking change when migrating from v1 to v2. Each section includes before/after examples to help you update your integration quickly.

---

## Breaking Changes

### 1. Endpoint Path Prefix

All endpoints now live under `/v2/` instead of the root path.

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

### 2. Authentication Header

The auth header has changed from a custom header to a standard Bearer token.

**Before (v1):**
```http
X-Auth-Token: your_api_key_here
```

**After (v2):**
```http
Authorization: Bearer your_api_token_here
```

Requests sent with `X-Auth-Token` will now receive `401 Unauthorized`.

---

### 3. Task ID Type: Integer → UUID

Task IDs are no longer integers. They are now UUID strings.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

Update any code that parses or stores task IDs to expect a string instead of an integer. This affects URL parameters, database columns, and response parsing.

---

### 4. Field Renamed: `done` → `completed`

The `done` boolean field has been renamed to `completed`.

**Before (v1):**
```json
{
  "title": "Write tests",
  "done": true
}
```

**After (v2):**
```json
{
  "title": "Write tests",
  "completed": true
}
```

Update all request bodies and response handling to use `completed` instead of `done`.

---

### 5. Task Creation Requires `project_id`

Creating a task now requires a `project_id` field. Omitting it returns `422 Unprocessable Entity`.

**Before (v1):**
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

**After (v2):**
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

You must provision a project before creating tasks. Pass the `project_id` as a required field in every task creation request.

---

### 6. List Response Format: Bare Array → Paginated Envelope

List endpoints no longer return a bare array. They return a pagination envelope with `items`, `total`, and `next_cursor`.

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
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Update your list parsing code to read from `response.items` instead of the root array. Use `response.next_cursor` with a `?cursor=` query parameter to paginate through results. The default page size is 20; override with `?limit=` (max 100).

---

## Migration Checklist

- [ ] Update all endpoint URLs from `/tasks` to `/v2/tasks`
- [ ] Change auth header from `X-Auth-Token` to `Authorization: Bearer <token>`
- [ ] Update task ID handling: integer → UUID string
- [ ] Rename `done` field to `completed` in request bodies and response parsing
- [ ] Add `project_id` to all task creation requests
- [ ] Update list response parsing: read from `items` array, use `next_cursor` for pagination
- [ ] Update integration tests to reflect the new response shapes
- [ ] Audit any stored task IDs — migrate integers to UUID strings if applicable
- [ ] Review code that handles `422` responses for missing `project_id`

---

## Upgrading

To upgrade the Zrb CLI to v2:

```bash
npm install -g @zrb/cli@latest
```

Or if you prefer yarn:

```bash
yarn global add @zrb/cli@latest
```

After upgrading, verify the installation:

```bash
zrb --version
```
