# Zrb CLI v2 Migration Guide

This document will guide you through the migration from Zrb CLI v1 to v2, highlighting breaking changes and providing examples for a smooth transition.

## Breaking Changes

### 1. Endpoint Prefix

All endpoints are now prefixed with `/v2/`.

**v1 Example:**
```http
GET /tasks
```

**v2 Example:**
```http
GET /v2/tasks
```

### 2. Authentication Header Change

The header used for authentication has changed.

**v1 Example:**
```
X-Auth-Token: <your_api_key>
```

**v2 Example:**
```
Authorization: Bearer <your_api_token>
```

### 3. Task ID as UUID

Task IDs are now UUID strings instead of integers.

**v1 Example:**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**v2 Example:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

### 4. Renaming `done` to `completed`

The task field `done` has been renamed to `completed`.

**v1 Example:**
```json
{
  "done": true
}
```

**v2 Example:**
```json
{
  "completed": true
}
```

### 5. Task Creation Requires `project_id`

Creating tasks now requires specifying `project_id`.

**v1 Example:**
```json
{
  "title": "New task title"
}
```

**v2 Example:**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Endpoints

Endpoints now return a paginated envelope instead of a bare array.

**v1 Example:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**v2 Example:**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false},
    {"id": "123e4567-e89b-12d3-a456-426614174000", "title": "Ship v1", "completed": true}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

1. **Update HTTP request paths** to include the `/v2/` prefix.
2. **Change authentication header** from `X-Auth-Token` to `Authorization: Bearer`.
3. **Modify code to handle UUIDs** for task IDs.
4. **Rename all instances of `done` to `completed`** in your task management logic.
5. **Ensure `project_id` is included** in task creation requests.
6. **Adapt to paginated list responses**, incorporating cursor-based pagination.

## Upgrade Command

To upgrade to Zrb CLI v2, run:

```bash
npm install -g zrb-cli@2
```

With these steps, your application should be fully compatible with Zrb API v2.
