# Migrating to Zrb CLI v2

Zrb CLI v2 introduces significant improvements to project management, pagination, and security. Because of these changes, v2 is not backward compatible with v1.

This guide will help you migrate your integrations from v1 to v2.

## Breaking Changes

### 1. API Endpoint Versioning
All endpoints are now prefixed with `/v2/`.

**v1**
`GET /tasks`

**v2**
`GET /v2/tasks`

---

### 2. Authentication Header
Authentication has moved from a custom token header to a standard Bearer token.

**v1**
```http
X-Auth-Token: <your_api_key>
```

**v2**
```http
Authorization: Bearer <your_api_token>
```

---

### 3. Task ID Type
Task IDs have changed from integers to UUID strings to support better distribution and scaling.

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

### 4. Field Rename: `done` $\rightarrow$ `completed`
The `done` boolean field has been renamed to `completed` for better clarity.

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

### 5. Required `project_id` on Creation
Tasks can no longer be created without being associated with a project. The `project_id` field is now mandatory.

**v1**
```json
{
  "title": "New task"
}
```

**v2**
```json
{
  "title": "New task",
  "project_id": "proj_abc123"
}
```

---

### 6. Paginated List Responses
List endpoints no longer return a bare array. They now return a paginated envelope containing metadata and a cursor for subsequent requests.

**v1**
```json
[
  {"id": 1, "title": "Buy milk", "completed": false},
  {"id": 2, "title": "Ship v1", "completed": true}
]
```

**v2**
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

- [ ] Update all base URLs to include the `/v2/` prefix.
- [ ] Update authentication logic to use the `Authorization: Bearer` header.
- [ ] Update data models to handle `id` as a string (UUID) instead of an integer.
- [ ] Rename all references of the `done` field to `completed` in request and response handlers.
- [ ] Ensure all `POST /v2/tasks` requests include a valid `project_id`.
- [ ] Update list-handling logic to parse the `items` array from the new paginated envelope.
- [ ] Implement cursor-based pagination using the `next_cursor` and `?cursor=` query parameter.

## Upgrade Command

To upgrade your CLI to the latest version, run:

```bash
zrb upgrade --version v2
```
