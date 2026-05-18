# Migrating to Zrb CLI v2

Zrb CLI v2 introduces significant improvements to project organization, authentication, and API scalability. Because of these changes, v2 is not backward compatible with v1.

This guide will help you migrate your existing integrations to the v2 API.

## Breaking Changes

### 1. API Version Prefix
All endpoints have been moved to a new versioned path.
- **v1**: `/tasks`
- **v2**: `/v2/tasks`

### 2. Authentication Header
We have moved from a custom token header to the standard Bearer token format.

**v1**
```http
X-Auth-Token: <your_api_key>
```

**v2**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task IDs (Integer to UUID)
Task IDs are no longer integers. They are now representative UUID strings to support distributed systems.

**v1**
```json
{ "id": 42 }
```

**v2**
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
```

### 4. Field Rename: `done` $\rightarrow$ `completed`
The `done` boolean field has been renamed to `completed` for better clarity.

**v1**
```json
{ "done": true }
```

**v2**
```json
{ "completed": true }
```

### 5. Required `project_id` on Creation
Tasks must now belong to a project. When creating a task, `project_id` is now a required field.

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
List endpoints no longer return a bare array. They now return a paginated envelope to improve performance for large data sets.

**v1**
```json
[
  {"id": 1, "title": "Task 1", ...},
  {"id": 2, "title": "Task 2", ...}
]
```

**v2**
```json
{
  "items": [
    {"id": "uuid-1", "title": "Task 1", ...},
    {"id": "uuid-2", "title": "Task 2", ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist

- [ ] Update base URL endpoints to include the `/v2/` prefix.
- [ ] Update authentication logic to use the `Authorization: Bearer` header.
- [ ] Update data models to handle UUID strings instead of integers for `id`.
- [ ] Rename all references of the `done` field to `completed`.
- [ ] Modify task creation logic to include a valid `project_id`.
- [ ] Update list request handlers to parse the `items` array from the paginated envelope.
- [ ] Implement cursor-based pagination using the `next_cursor` value.

## Upgrade Command

To upgrade your CLI to the latest version, run:

```bash
zrb upgrade --version v2
```
