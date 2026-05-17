# Zrb v2 Migration Guide

This guide details the breaking changes introduced in Zrb v2 and provides the necessary steps to migrate your application from v1. v2 introduces project-based organization, improved pagination, and enhanced security.

## 1. Base URL Versioning
All API endpoints are now versioned. You must update your client configuration to use the `/v2/` prefix for all requests.

**v1 (Before)**
```http
GET /tasks
```

**v2 (After)**
```http
GET /v2/tasks
```

## 2. Authentication Header
The authentication mechanism has transitioned to the standard Bearer token format. The `X-Auth-Token` header is deprecated and will return a `401 Unauthorized` error.

**v1 (Before)**
```http
X-Auth-Token: <your_api_key>
```

**v2 (After)**
```http
Authorization: Bearer <your_api_token>
```

## 3. Task ID Type Change
Task IDs have changed from auto-incrementing integers to UUID strings to better support distributed systems. Ensure your local data structures and database schemas are updated to handle string-based UUIDs.

**v1 (Before)**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**v2 (After)**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

## 4. Field Renaming: `done` to `completed`
The `done` field has been renamed to `completed` across all responses and request bodies for better clarity.

**v1 (Before)**
```json
{
  "title": "Ship v1",
  "done": true
}
```

**v2 (After)**
```json
{
  "title": "Ship v1",
  "completed": true
}
```

## 5. Required `project_id` for Task Creation
Tasks must now be associated with a project. The `project_id` field is now mandatory when creating a new task; omitting it will result in a `422 Unprocessable Entity` error.

**v1 (Before)**
```json
POST /tasks
{
  "title": "New task title"
}
```

**v2 (After)**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

## 6. Paginated List Responses
The list endpoint (`GET /v2/tasks`) no longer returns a bare array. It now returns a paginated envelope to support large datasets efficiently.

**v1 (Before)**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**v2 (After)**
```json
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false},
    {"id": "...", "title": "Ship v1", "completed": true}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist
- [ ] Update API base URL to include the `/v2/` prefix.
- [ ] Update authentication logic to use the `Authorization: Bearer <token>` header.
- [ ] Update Task data models to support UUID strings for the `id` field.
- [ ] Replace all references to the `done` field with `completed`.
- [ ] Modify task creation calls to include a valid `project_id`.
- [ ] Refactor list response parsing to handle the new paginated envelope (`items` array).
- [ ] (Optional) Implement cursor-based pagination using the `next_cursor` property.

## Upgrade Command
To upgrade the Zrb CLI to the latest version, run:

```bash
npm install -g zrb@latest
```
