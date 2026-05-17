# Migrating to Zrb CLI v2

Welcome to Zrb v2. This version introduces structural changes to improve scalability, including project-based task organization and paginated API responses. Because of these improvements, v2 includes several breaking changes from v1.

This guide will help you migrate your existing integrations and scripts to the new API.

## Breaking Changes

### 1. API Endpoint Prefixing
All API endpoints are now prefixed with `/v2/`. Requests to v1 endpoints are no longer supported.

**v1**
`GET /tasks`

**v2**
`GET /v2/tasks`

---

### 2. Authentication Header
Authentication has moved from a custom header to the industry-standard Bearer token.

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
Task IDs have changed from integers to UUID strings to support distributed project environments. Update your database schemas and type definitions accordingly.

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

### 4. Status Field Rename
The `done` field has been renamed to `completed` for better clarity.

**v1**
```json
{
  "done": true
}
```

**v2**
```json
{
  "completed": true
}
```

---

### 5. Required Project Association
Tasks can no longer exist in a global namespace. Every new task must be associated with a `project_id`.

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
List endpoints no longer return a bare array. They now return a paginated envelope containing the items, a total count, and a cursor for the next page.

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

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Update authentication logic to use `Authorization: Bearer <token>`.
- [ ] Update data models to treat task `id` as a string (UUID) instead of an integer.
- [ ] Rename occurrences of the `done` field to `completed` in request and response handling.
- [ ] Identify or create `project_id`s to include in all `POST /v2/tasks` requests.
- [ ] Implement cursor-based pagination logic for all list endpoints.

## Upgrade Command

To update your CLI tools to the latest version, run:

```bash
zrb update --version 2.0.0
```
