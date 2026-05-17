# Migrating to Zrb CLI v2

Zrb CLI v2 introduces several breaking changes to improve scalability, security, and organization. This guide will help you transition your integration from v1 to v2.

## Breaking Changes

### 1. API Endpoint Prefixing
All API endpoints now require a `/v2/` prefix.

**v1**
`GET /tasks`

**v2**
`GET /v2/tasks`

---

### 2. Authentication Header
The authentication mechanism has moved from a custom header to a standard Bearer token.

**v1**
```http
X-Auth-Token: <your_api_key>
```

**v2**
```http
Authorization: Bearer <your_api_token>
```

---

### 3. Task ID Format
Task IDs have changed from integers to UUID strings. Ensure your database schemas and variable types are updated to handle strings.

**v1**
```json
{ "id": 42 }
```

**v2**
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
```

---

### 4. Task Completion Field
The field `done` has been renamed to `completed` for better clarity.

**v1**
```json
{ "done": false }
```

**v2**
```json
{ "completed": false }
```

---

### 5. Required Project ID on Creation
Tasks must now be associated with a project. The `project_id` field is now mandatory when creating a task.

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
List endpoints no longer return a bare array. They now return a paginated envelope containing the items and a cursor for subsequent requests.

**v1**
```json
[
  {"id": 1, "title": "Buy milk", ...},
  {"id": 2, "title": "Ship v1", ...}
]
```

**v2**
```json
{
  "items": [
    {"id": "...", "title": "Buy milk", ...},
    {"id": "...", "title": "Ship v1", ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Switch authentication from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Update data models to treat `Task.id` as a string (UUID).
- [ ] Replace all references to the `done` field with `completed`.
- [ ] Update task creation logic to provide a valid `project_id`.
- [ ] Update list response handling to extract data from the `items` array and implement cursor-based pagination.

## Upgrade Command

To upgrade your CLI to the latest version, run:

```bash
zrb update --version v2
```
