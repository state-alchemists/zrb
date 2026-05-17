# Zrb v2 Migration Guide

Zrb v2 introduces projects, improved pagination, and stricter authentication. This guide outlines the breaking changes from v1 and provides a step-by-step path to upgrade your integrations.

## Breaking Changes

### 1. New Base URL Prefix
All API endpoints now require a `/v2/` prefix.

**Before:**
`GET /tasks`

**After:**
`GET /v2/tasks`

---

### 2. Standardized Authentication
Authentication has moved from a custom header to the standard `Authorization` Bearer scheme.

**Before:**
```http
X-Auth-Token: your_api_key
```

**After:**
```http
Authorization: Bearer your_api_token
```

---

### 3. Task ID Type Change
Task IDs have changed from auto-incrementing integers to UUID strings to better support distributed environments and future project features.

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

### 4. Field Renaming: `done` to `completed`
The `done` field on Task objects has been renamed to `completed` for consistency with broader industry naming conventions.

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

### 5. Mandatory `project_id` for Task Creation
Tasks must now belong to a project. When creating a task, you must provide a valid `project_id`.

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
List endpoints no longer return a bare array. Instead, they return a paginated envelope containing metadata and a cursor for fetching subsequent pages.

**Before:**
```json
[
  {"id": 1, "title": "Buy milk"},
  {"id": 2, "title": "Ship v1"}
]
```

**After:**
```json
{
  "items": [
    {"id": "...", "title": "Buy milk"},
    {"id": "...", "title": "Ship v1"}
  ],
  "total": 2,
  "next_cursor": null
}
```

---

## Migration Checklist

1. [ ] **Update Auth Header**: Switch from `X-Auth-Token` to `Authorization: Bearer`.
2. [ ] **Update Base URLs**: Append `/v2/` to all API request paths.
3. [ ] **Refactor ID Handling**: Update your data models and logic to handle UUID strings instead of integers.
4. [ ] **Rename Fields**: Update all references to the `done` field to use `completed`.
5. [ ] **Inject Project IDs**: Ensure your `POST /v2/tasks` calls include a `project_id`.
6. [ ] **Update List Parsing**: Adjust your response parsing logic to extract items from the `.items` property of the new paginated envelope.
7. [ ] **Implement Pagination**: If you have many tasks, update your list logic to use the `next_cursor` and `?cursor=` query parameter.

## Upgrade Command

To upgrade the Zrb CLI to the latest version, run:

```bash
pip install --upgrade zrb
```
