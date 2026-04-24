# Zrb v2 Migration Guide

This guide provides everything you need to migrate your integrations from Zrb v1 to Zrb v2. v2 introduces projects, improved pagination, and stricter authentication requirements.

## Breaking Changes

### 1. New API Prefix
All API endpoints are now versioned. You must prefix all requests with `/v2/`.

**Before:**
`GET /tasks`

**After:**
`GET /v2/tasks`

---

### 2. Authentication Header
The custom `X-Auth-Token` header has been deprecated in favor of the standard `Authorization` Bearer token scheme.

**Before:**
```http
X-Auth-Token: <your_api_key>
```

**After:**
```http
Authorization: Bearer <your_api_token>
```

---

### 3. Task ID Type Change
Task IDs have migrated from auto-incrementing integers to UUID strings to better support distributed systems and projects.

**Before:**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**After:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

---

### 4. Field Rename: `done` to `completed`
To improve clarity, the `done` boolean field on task objects has been renamed to `completed`.

**Before:**
```json
{
  "title": "Buy milk",
  "done": false
}
```

**After:**
```json
{
  "title": "Buy milk",
  "completed": false
}
```

---

### 5. Mandatory Project ID for Task Creation
Tasks are now organized into projects. Every new task must be associated with a `project_id`.

**Before:**
```json
POST /tasks
{
  "title": "New task title"
}
```

**After:**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

### 6. Paginated List Responses
List endpoints no longer return a bare array. They now return a paginated envelope containing metadata and a cursor for fetching subsequent pages.

**Before:**
```json
[
  {"id": 1, "title": "Buy milk", ...},
  {"id": 2, "title": "Ship v1", ...}
]
```

**After:**
```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", ...},
    {"id": "c3d4...", "title": "Ship v1", ...}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` headers with `Authorization: Bearer <token>`.
- [ ] Update Task data models to accept UUID strings for the `id` field.
- [ ] Rename the `done` field to `completed` in your application logic and UI.
- [ ] Update task creation logic to include the required `project_id`.
- [ ] Refactor list handling to extract task items from the new paginated envelope (`.items`).
- [ ] Implement cursor-based pagination logic using the `next_cursor` field if needed.

## Upgrade Command

To update your Zrb CLI to the latest version, run:

```bash
zrb upgrade
```
