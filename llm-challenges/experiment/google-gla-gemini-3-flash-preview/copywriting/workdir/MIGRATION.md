# Zrb v2 Migration Guide

This guide provides the necessary steps to migrate your application from Zrb v1 to v2. Version 2 introduces project-based task management, improved pagination, and enhanced security standards.

## Breaking Changes

### 1. API Endpoint Prefixing
All API endpoints are now versioned. You must prefix your request paths with `/v2/`.

**Before (v1):**
`GET /tasks`

**After (v2):**
`GET /v2/tasks`

---

### 2. Authentication Header
The proprietary `X-Auth-Token` header has been replaced with the standard `Authorization` Bearer token format. Requests using the old header will now return a `401 Unauthorized` error.

**Before (v1):**
```http
X-Auth-Token: your_api_key
```

**After (v2):**
```http
Authorization: Bearer your_api_token
```

---

### 3. Task ID Type Change
To support distributed systems and prevent ID scraping, Task `id` fields have changed from auto-incrementing integers to UUID strings.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

---

### 4. Field Rename: `done` to `completed`
The boolean field indicating task status has been renamed from `done` to `completed` for better clarity across the platform.

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

---

### 5. Required `project_id` for Task Creation
Tasks can no longer exist in isolation. Every task must be associated with a project. You must include a valid `project_id` when creating a task.

**Before (v1):**
```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

### 6. Paginated Response Envelopes
List endpoints (such as `GET /v2/tasks`) no longer return a bare array. They now return a paginated envelope containing metadata and a cursor for fetching subsequent pages.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk"},
  {"id": 2, "title": "Ship v1"}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk"},
    {"id": "uuid-2", "title": "Ship v1"}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] **Prefix Endpoints**: Update all API call URLs to include the `/v2/` segment.
- [ ] **Update Auth**: Change your header implementation to use `Authorization: Bearer <token>`.
- [ ] **Refactor IDs**: Update your data models and database schemas to store Task IDs as strings/UUIDs instead of integers.
- [ ] **Rename Fields**: Search and replace `done` with `completed` in your frontend components and backend logic.
- [ ] **Add Project Context**: Ensure your task creation workflow captures and sends a `project_id`.
- [ ] **Handle Pagination**: Update your list fetching logic to extract data from the `items` key and implement cursor-based pagination using `next_cursor`.

## Upgrade Command

To install the latest version of the Zrb CLI, run:

```bash
pip install --upgrade zrb
```
