# Migrating to Zrb CLI v2

Zrb CLI v2 introduces several breaking changes to the Task API to support projects, improved scalability, and better security. This guide will help you migrate your existing v1 integrations to v2.

## Breaking Changes

### 1. Endpoint Versioning
All API endpoints now require a `/v2/` prefix. Requests made to v1 endpoints are no longer supported.

**v1**
`GET /tasks`

**v2**
`GET /v2/tasks`

---

### 2. Authentication Header
The API has moved from a custom token header to the industry-standard Bearer token authentication.

**v1**
```http
X-Auth-Token: <your_api_key>
```

**v2**
```http
Authorization: Bearer <your_api_token>
```

---

### 3. Task ID Type Change
Task IDs have changed from integers to UUID strings to prevent ID enumeration and improve distributed system reliability.

**v1**
```json
{
  "id": 42
}
```

**v2**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

### 4. Field Rename: `done` → `completed`
The `done` property on the Task object has been renamed to `completed` for better clarity.

**v1**
```json
{
  "title": "Write tests",
  "done": false
}
```

**v2**
```json
{
  "title": "Write tests",
  "completed": false
}
```

---

### 5. Required Project Association
Tasks can no longer exist in isolation. Every new task must be associated with a project via a `project_id`.

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

### 6. Paginated List Responses
List endpoints no longer return a bare array. They now return a paginated envelope to handle large datasets efficiently.

**v1**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**v2**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false},
    {"id": "uuid-2", "title": "Ship v1", "completed": true}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update base URL/endpoints to include the `/v2/` prefix.
- [ ] Update authentication logic to use `Authorization: Bearer <token>`.
- [ ] Update data models to treat task IDs as strings (UUIDs).
- [ ] Rename all occurrences of the `done` field to `completed` in requests and responses.
- [ ] Update task creation logic to include a valid `project_id`.
- [ ] Update list response handling to extract data from the `items` array and implement cursor-based pagination.

## Upgrade Command

To upgrade your local CLI to v2, run:

```bash
zrb upgrade --version 2.0.0
```
