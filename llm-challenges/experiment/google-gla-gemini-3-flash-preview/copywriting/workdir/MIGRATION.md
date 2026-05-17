# Zrb v2 Migration Guide

Zrb v2 introduces significant improvements to the Task API, including project support, enhanced pagination, and more secure authentication. This guide outlines the breaking changes from v1 and provides the steps necessary to upgrade your integrations.

## Breaking Changes

### 1. New API Prefix
All API endpoints are now prefixed with `/v2/`.

**v1 (Old):**
```http
GET /tasks
```

**v2 (New):**
```http
GET /v2/tasks
```

### 2. Authentication Header Change
The custom `X-Auth-Token` header has been replaced by the standard `Authorization` Bearer token scheme.

**v1 (Old):**
```http
X-Auth-Token: your_api_key
```

**v2 (New):**
```http
Authorization: Bearer your_api_token
```

### 3. Task ID Type Change
Task identifiers have changed from integers to UUID strings to better support distributed systems and project isolation.

**v1 (Old):**
```json
{
  "id": 42
}
```

**v2 (New):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Field Rename: `done` to `completed`
The `done` boolean field on Task objects has been renamed to `completed` for better clarity.

**v1 (Old):**
```json
{
  "title": "Write tests",
  "done": false
}
```

**v2 (New):**
```json
{
  "title": "Write tests",
  "completed": false
}
```

### 5. Mandatory `project_id` on Creation
Tasks must now belong to a project. The `project_id` field is now required when creating a new task.

**v1 (Old):**
```json
POST /tasks
{
  "title": "New task"
}
```

**v2 (New):**
```json
POST /v2/tasks
{
  "title": "New task",
  "project_id": "proj_abc123"
}
```

### 6. List Response Envelope & Pagination
List endpoints no longer return a bare array. They now return a paginated envelope containing an `items` array and pagination metadata.

**v1 (Old):**
```json
[
  {"id": 1, "title": "Buy milk", ...},
  {"id": 2, "title": "Ship v1", ...}
]
```

**v2 (New):**
```json
{
  "items": [
    {"id": "...", "title": "Buy milk", ...},
    {"id": "...", "title": "Ship v2", ...}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, use the `cursor` query parameter: `GET /v2/tasks?cursor=cursor_xyz`.

## Migration Checklist

- [ ] Update the base URL for all API requests to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token: <key>` headers with `Authorization: Bearer <token>`.
- [ ] Update your data models and database schemas to accept UUID strings for task `id`.
- [ ] Update all references to the `done` field to use `completed`.
- [ ] Modify task creation logic to include the mandatory `project_id`.
- [ ] Refactor list processing logic to handle the new `{ items, total, next_cursor }` response envelope.
- [ ] Implement cursor-based pagination for large result sets.

## Upgrade Command

To update the Zrb CLI to the latest version, run:

```bash
pip install --upgrade zrb
```
