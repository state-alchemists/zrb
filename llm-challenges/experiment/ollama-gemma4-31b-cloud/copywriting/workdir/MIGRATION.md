# Migrating to Zrb CLI v2

Welcome to the v2 migration guide. Zrb v2 introduces several breaking changes to improve scalability, security, and organization through the introduction of projects and improved pagination.

## Breaking Changes

### 1. API Endpoint Prefixing
All API endpoints are now versioned. You must prefix your request paths with `/v2/`.

**v1:**
`GET /tasks`

**v2:**
`GET /v2/tasks`

### 2. Authentication Header
The authentication mechanism has shifted from a custom header to a standard Bearer token.

**v1:**
```http
X-Auth-Token: <your_api_key>
```

**v2:**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task ID Type Change
Task IDs have moved from integers to UUID strings to ensure uniqueness across distributed systems. Ensure your client-side data models can handle strings instead of numbers.

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

### 4. Field Rename: `done` → `completed`
The boolean field indicating task completion has been renamed for clarity.

**v1:**
```json
{
  "title": "Ship v1",
  "done": true
}
```

**v2:**
```json
{
  "title": "Ship v1",
  "completed": true
}
```

### 5. Mandatory Project Association
Tasks can no longer exist in a vacuum. Every new task must be associated with a project via a `project_id`.

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

### 6. List Response Pagination
List endpoints no longer return a bare array. They now return a paginated envelope to improve performance with large datasets.

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
    {"id": "...", "title": "Buy milk", "completed": false},
    {"id": "...", "title": "Ship v1", "completed": true}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Update authentication headers from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Update data models to treat `id` as a string (UUID) rather than an integer.
- [ ] Replace all occurrences of the `done` field with `completed` in requests and response handling.
- [ ] Update task creation logic to include a valid `project_id`.
- [ ] Update list endpoint handlers to parse the `items` array from the new paginated envelope.
- [ ] Implement cursor-based pagination using `next_cursor` if fetching large lists.

## Upgrade Command

To upgrade your CLI to the latest version, run:

```bash
zrb upgrade --version v2
```
