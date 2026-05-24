# Migrating to Zrb CLI v2

Zrb v2 introduces significant architectural improvements, including the introduction of projects and a more robust pagination system. These changes are breaking and require manual updates to your integration.

## Breaking Changes

### 1. API Versioning
All endpoints are now prefixed with `/v2/` to ensure stable versioning.

**v1**
`GET /tasks`

**v2**
`GET /v2/tasks`

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

### 3. Task Identifiers
Task `id`s have transitioned from integers to UUID strings for better distribuability.

**v1**
```json
{ "id": 42, "title": "Write tests" }
```

**v2**
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests" }
```

### 4. Field Rename: `done` → `completed`
The `done` field has been renamed to `completed` for clarity.

**v1**
```json
{ "title": "Update docs", "done": true }
```

**v2**
```json
{ "title": "Update docs", "completed": true }
```

### 5. Required Projects for Task Creation
Tasks must now be associated with a project. Providing a `project_id` is mandatory when creating a task.

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

### 6. Paginated List Responses
List endpoints no longer return a bare array. They now return a paginated envelope containing the items and navigation cursors.

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
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update all API endpoints to include the `/v2/` prefix.
- [ ] Change authentication header from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Update Task `id` handling logic from `integer` to `string` (UUID).
- [ ] Replace all references to the `done` field with `completed`.
- [ ] Update task creation logic to include a mandatory `project_id`.
- [ ] Update list response parsing to extract data from the `items` array within the response envelope.
- [ ] Implement cursor-based pagination using `next_cursor`.

## Upgrade Command

Update your Zrb CLI to the latest version:

```bash
zrb update --version 2.0.0
```
