# Migrating to Zrb CLI v2

Zrb CLI v2 introduces significant improvements to project management and API scalability. Because of these changes, v2 is not backward compatible with v1. This guide will help you migrate your integration.

## Breaking Changes

### 1. API Endpoint Versioning
All API endpoints now require the `/v2/` prefix.

**v1**
`GET /tasks`

**v2**
`GET /v2/tasks`

---

### 2. Authentication Header
Authentication has moved from a custom header to the standard Bearer token format.

**v1**
```http
X-Auth-Token: <<youryour_api_key>
```

**v2**
```http
Authorization: Bearer <<youryour_api_token>
```

---

### 3. Task ID Data Type
Task IDs have changed from integers to UUID strings to support better distributed scaling.

**v1**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**v2**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

---

### 4. Property Rename: `done` → `completed`
The boolean property indicating task status has been renamed for clarity.

**v1**
```json
{
  "title": "Update docs",
  "done": true
}
```

**v2**
```json
{
  "title": "Update docs",
  "completed": true
}
```

---

### 5. Mandatory Project Association
Tasks can no longer exist in isolation. You must now provide a `project_id` when creating a task.

**v1**
```json
{
  "title": "New task title"
}
```

**v2**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

### 6. List Response Format (Pagination)
List endpoints no longer return a bare array. They now return a paginated envelope to ensure performance with large datasets.

**v1**
```json
[
  {"id": 1, "title": "Task 1", "done": false},
  {"id": 2, "title": "Task 2", "done": true}
]
```

**v2**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Task 1", "completed": false},
    {"id": "uuid-2", "title": "Task 2", "completed": true}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Update authentication logic to use `Authorization: Bearer` instead of `X-Auth-Token`.
- [ ] Update data models to handle `id` as a string (UUID) instead of an integer.
- [ ] Replace all references to the `done` field with `completed`.
- [ ] Update task creation logic to include a valid `project_id`.
- [ ] Update list response handling to extract data from the `items` array and implement cursor-based pagination.

## Upgrade Command

To upgrade your CLI to the latest version, run:

```bash
zrb upgrade --version v2
```
