# Zrb API v1 to v2 Migration Guide

The Zrb API v2 introduces projects, improved pagination, and stricter authentication. This guide outlines all breaking changes from v1 and provides a step-by-step migration path for existing integrations.

## Breaking Changes

### 1. Endpoint Path Prefix
All API endpoints are now prefixed with `/v2/`.

**Before:**
```http
GET /tasks
```

**After:**
```http
GET /v2/tasks
```

### 2. Authentication Header
The custom `X-Auth-Token` header has been replaced by the standard `Authorization` header using the `Bearer` scheme.

**Before:**
```http
X-Auth-Token: <your_api_key>
```

**After:**
```http
Authorization: Bearer <your_api_key>
```

### 3. Task ID Type Change
Task IDs are now UUID strings instead of auto-incrementing integers. Update your local database schemas and type definitions accordingly.

**Before:**
```json
{
  "id": 42
}
```

**After:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Task Completion Field Renamed
The boolean field indicating whether a task is finished has been renamed from `done` to `completed`.

**Before:**
```json
{
  "title": "Write tests",
  "done": true
}
```

**After:**
```json
{
  "title": "Write tests",
  "completed": true
}
```

### 5. Project ID Required on Creation
Task creation now strictly requires a `project_id`. Requests without it will be rejected with an HTTP 422 error.

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
The `GET /v2/tasks` endpoint no longer returns a bare JSON array. It returns a paginated envelope object containing `items`, `total`, and a `next_cursor`.

**Before:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
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

## Migration Checklist

- [ ] Prefix all API request URLs with `/v2/`.
- [ ] Switch from the `X-Auth-Token` header to `Authorization: Bearer <token>`.
- [ ] Migrate your database schema and types to handle `id` as a UUID string instead of an integer.
- [ ] Find and replace all references to the `done` field with `completed`.
- [ ] Update your task creation logic to include a valid `project_id`.
- [ ] Refactor task list parsing to extract the array from the `.items` property of the new response envelope.
- [ ] (Optional) Implement pagination handling using the `.next_cursor` field.

## Upgrade Command

To upgrade to the v2 release, run:

```bash
pip install --upgrade zrb
```
