# Migrating to Zrb CLI v2

Zrb CLI v2 introduces a more robust architecture featuring project organization, standardized UUIDs, and improved pagination. Because these changes improve the foundation of the API, v2 includes several breaking changes.

This guide will help you transition your integrations from v1 to v2.

## Breaking Changes

### 1. API Versioning & Endpoints
All API endpoints are now prefixed with `/v2/`.

**v1**
`GET /tasks`

**v2**
`GET /v2/tasks`

---

### 2. Authentication Header
Authentication has moved from a custom header to the industry-standard Bearer token. Requests using the old header will return `401 Unauthorized`.

**v1**
```http
X-Auth-Token: <your_api_key>
```

**v2**
```http
Authorization: Bearer <your_api_token>
```

---

### 3. Task Identification (ID Type)
Task IDs have changed from integers to UUID strings to support better distributed scaling and project isolation.

**v1**
```json
{ "id": 42 }
```

**v2**
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
```

---

### 4. Field Rename: `done` → `completed`
To provide better clarity, the `done` boolean has been renamed to `completed`.

**v1**
```json
{ "done": false }
```

**v2**
```json
{ "completed": false }
```

---

### 5. Mandatory Project Association
Tasks can no longer exist in a vacuum. Every new task must be associated with a project via a `project_id`. Omitting this field will result in a `422 Unprocessable Entity` error.

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
  {"id": 1, "title": "Buy milk"},
  {"id": 2, "title": "Ship v1"}
]
```

**v2**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk"},
    {"id": "uuid-2", "title": "Ship v1"}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update base URL/endpoints to include the `/v2/` prefix.
- [ ] Switch authentication header from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Update data models to handle `id` as a string (UUID) instead of an integer.
- [ ] Replace all references to the `done` field with `completed`.
- [ ] Update task creation logic to include a valid `project_id`.
- [ ] Update list request handling to parse the `items` envelope and implement cursor-based pagination.

## Upgrade Command

To update your CLI to the latest version, run:

```bash
zrb update --version v2
```
