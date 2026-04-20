# Zrb CLI v2 Migration Guide

This guide assists developers in migrating their applications from Zrb v1 to v2. Version 2 introduces several breaking changes to improve performance, security, and scalability.

## Breaking Changes

### 1. Endpoint Prefixing
All API endpoints are now prefixed with `/v2/`. Requests to the root `/tasks` path will no longer work.

**Before:**
`GET /tasks`

**After:**
`GET /v2/tasks`

---

### 2. Authentication Header
The authentication mechanism has moved from a custom header to the standard `Authorization` Bearer scheme.

**Before:**
```http
X-Auth-Token: <your_api_key>
```

**After:**
```http
Authorization: Bearer <your_api_token>
```

---

### 3. Task ID Type
Task IDs have transitioned from integers to UUID strings to better support distributed environments.

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

### 4. Renamed Field: `done` to `completed`
The `done` boolean field on Task objects has been renamed to `completed` for better clarity.

**Before:**
```json
{
  "title": "Write tests",
  "done": false
}
```

**After:**
```json
{
  "title": "Write tests",
  "completed": false
}
```

---

### 5. Required `project_id` on Creation
Tasks must now belong to a project. The `project_id` field is now mandatory when creating a new task.

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

### 6. Paginated List Response
List endpoints now return a paginated envelope instead of a bare array. This allows for better handling of large datasets via cursor-based pagination.

**Before:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**After:**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false},
    {"id": "uuid-2", "title": "Ship v1", "completed": true}
  ],
  "total": 2,
  "next_cursor": null
}
```

## Migration Checklist

- [ ] Update the base API URL to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` headers with `Authorization: Bearer <token>`.
- [ ] Update data models and database schemas to store IDs as UUID strings.
- [ ] Rename all occurrences of the `done` field to `completed` in your application logic and UI templates.
- [ ] Modify task creation logic to include a valid `project_id`.
- [ ] Refactor list-fetching logic to extract data from the `items` property of the new response envelope.
- [ ] (Optional) Implement cursor-based pagination using the `next_cursor` field and `?cursor=` query parameter.

## Upgrade Command

To upgrade your CLI to the latest version, run:

```bash
npm install -g zrb@latest
```
