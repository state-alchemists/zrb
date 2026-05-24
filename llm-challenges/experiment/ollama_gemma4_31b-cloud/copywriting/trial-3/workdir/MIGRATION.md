# Migrating to Zrb CLI v2

Zrb CLI v2 introduces several breaking changes to the Task API to support projects, improved pagination, and tighter security. This guide will help you migrate your integration from v1 to v2.

## Breaking Changes

### 1. API Endpoint Prefix
All API endpoints are now prefixed with `/v2/`.

**v1:**
`GET /tasks`

**v2:**
`GET /v2/tasks`

---

### 2. Authentication Header
Authentication has moved from a custom header to a standard Bearer token. Requests using `X-Auth-Token` will now return `401 Unauthorized`.

**v1:**
```http
X-Auth-Token: <your_api_key>
```

**v2:**
```http
Authorization: Bearer <your_api_token>
```

---

### 3. Task ID Type Change
Task IDs have changed from integers to UUID strings. Ensure your database schemas and type definitions are updated to handle strings.

**v1:**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**v2:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

---

### 4. Task Field Rename: `done` → `completed`
The boolean field `done` has been renamed to `completed` for clarity.

**v1:**
```json
{
  "title": "Write tests",
  "done": false
}
```

**v2:**
```json
{
  "title": "Write tests",
  "completed": false
}
```

---

### 5. Required `project_id` on Creation
Tasks must now be associated with a project. The `project_id` field is now required when creating a task; omitting it will result in a `422 Unprocessable Entity` response.

**v1:**
```json
{
  "title": "New task title"
}
```

**v2:**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

---

### 6. Paginated List Responses
List endpoints no longer return a bare array. They now return a paginated envelope containing the items and a cursor for the next page.

**v1:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**v2:**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false},
    {"id": "uuid-2", "title": "Ship v1", "completed": true}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Switch authentication headers from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Update data models to treat Task IDs as strings (UUIDs) instead of integers.
- [ ] Rename all references to the `done` field to `completed`.
- [ ] Update task creation logic to include a valid `project_id`.
- [ ] Refactor list response handling to extract data from the `.items` array and implement cursor-based pagination.

## Upgrade Command

To upgrade your Zrb CLI to the latest version, run:

```bash
zrb update --version v2
```
