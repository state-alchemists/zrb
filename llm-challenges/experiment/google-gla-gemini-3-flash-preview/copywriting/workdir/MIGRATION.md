# Zrb v2 Migration Guide

Zrb v2 introduces several breaking changes to improve scalability, security, and project management. This guide outlines the steps required to upgrade your integration from v1 to v2.

## Breaking Changes

### 1. Endpoint Prefixing
All API endpoints are now versioned. You must prefix your existing routes with `/v2/`.

**Before:**
`GET /tasks`

**After:**
`GET /v2/tasks`

---

### 2. Authentication Header
The custom header `X-Auth-Token` has been deprecated in favor of the standard `Authorization` header with a `Bearer` scheme.

**Before:**
```http
X-Auth-Token: your_api_key
```

**After:**
```http
Authorization: Bearer your_api_token
```

---

### 3. UUID Identifiers
Task `id` fields have transitioned from auto-incrementing integers to UUID strings to better support distributed systems.

**Before:**
```json
{
  "id": 42
}
```

**After:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

### 4. Field Renaming: `done` to `completed`
To improve clarity, the `done` boolean field on Task objects is now named `completed`.

**Before:**
```json
{
  "title": "Ship v1",
  "done": true
}
```

**After:**
```json
{
  "title": "Ship v1",
  "completed": true
}
```

---

### 5. Required `project_id` for Task Creation
Tasks must now be associated with a project. The `project_id` field is now mandatory when creating a task.

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
List endpoints no longer return a bare array. They now return a paginated envelope containing metadata and a cursor for the next page.

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
    {"id": "uuid-1", "title": "Buy milk", ...},
    {"id": "uuid-2", "title": "Ship v1", ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update API base URL or resource paths to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`.
- [ ] Update data models to handle `id` as a UUID string instead of an integer.
- [ ] Rename the `done` property to `completed` in your Task models and UI.
- [ ] Update Task creation logic to include the mandatory `project_id`.
- [ ] Refactor list processing to handle the new paginated envelope structure (`.items`).

## Upgrade Command

To upgrade the Zrb CLI to the latest version, run:

```bash
zrb upgrade --v2
```
