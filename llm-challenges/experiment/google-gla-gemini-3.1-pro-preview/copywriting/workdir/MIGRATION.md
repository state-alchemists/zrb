# Zrb v2 Migration Guide

Zrb v2 introduces projects, improved pagination, and enhanced security. To support these features, the v2 API includes several breaking changes from v1.

This guide details how to update your integrations and workflows to support v2.

## Breaking Changes

### 1. Endpoint Prefix
All endpoints are now prefixed with `/v2/` to ensure predictable versioning.

**Before:**
```http
GET /tasks
```

**After:**
```http
GET /v2/tasks
```

### 2. Authentication Header
Authentication now strictly follows the OAuth 2.0 Bearer Token standard. The old `X-Auth-Token` header will return an HTTP 401.

**Before:**
```http
X-Auth-Token: <your_api_key>
```

**After:**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task IDs are now UUIDs
Task `id` types have migrated from auto-incrementing integers to UUID strings to support distributed creation. You must update your database schemas and type definitions accordingly.

**Before:**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**After:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

### 4. `done` renamed to `completed`
The boolean field tracking task status has been renamed from `done` to `completed` in both API requests (e.g., `PUT /v2/tasks/{id}`) and API responses.

**Before:**
```json
{
  "done": true
}
```

**After:**
```json
{
  "completed": true
}
```

### 5. `project_id` Required for Task Creation
Because v2 introduces projects, tasks can no longer exist globally. You must provide a `project_id` when creating a task. Omitting it will return an HTTP 422.

**Before:**
```json
// POST /tasks
{
  "title": "New task title"
}
```

**After:**
```json
// POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Responses
List endpoints (like `GET /v2/tasks`) no longer return a bare array. They return a paginated envelope containing `items`, `total`, and `next_cursor`.

**Before:**
```json
[
  { "id": 1, "title": "Buy milk", "done": false }
]
```

**After:**
```json
{
  "items": [
    { 
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", 
      "title": "Buy milk", 
      "completed": false, 
      "project_id": "proj_abc123" 
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```
*(Note: Pass `?cursor=<next_cursor>` to fetch subsequent pages.)*

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` headers with `Authorization: Bearer`.
- [ ] Update data models to handle `id` as a UUID string instead of an integer.
- [ ] Rename all code references from `done` to `completed`.
- [ ] Ensure all task creation POST requests include a valid `project_id`.
- [ ] Update list endpoint array mapping to map over `response.items` and implement cursor-based pagination.

## Upgrade Command

Ready to transition? Run the following to upgrade your Zrb CLI to v2:

```bash
zrb upgrade v2
```
