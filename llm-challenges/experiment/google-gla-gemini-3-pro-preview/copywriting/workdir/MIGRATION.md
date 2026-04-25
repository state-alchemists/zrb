# Zrb API v1 to v2 Migration Guide

Welcome to Zrb API v2. This release introduces projects, improved pagination, and stricter authentication. This guide outlines the breaking changes and provides a step-by-step checklist to migrate your v1 integration to v2.

## Breaking Changes

### 1. Endpoint Prefix Updated
All v2 API endpoints are now prefixed with `/v2/`.

**Before (v1):**
```http
GET /tasks
```

**After (v2):**
```http
GET /v2/tasks
```

### 2. Authentication Header Changed
The custom `X-Auth-Token` header has been replaced with the standard `Authorization` header using Bearer tokens. Using the old header will result in an HTTP `401 Unauthorized` error.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task ID Type Changed to UUID
Task `id` fields are now UUID strings instead of integers. You must update your database schemas, type definitions, and route parameters to accommodate strings.

**Before (v1):**
```json
{
  "id": 42
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Task Field `done` Renamed to `completed`
The boolean status field for a task has been renamed from `done` to `completed`. This applies to both responses and `PUT` request payloads.

**Before (v1):**
```json
{
  "title": "Write tests",
  "done": true
}
```

**After (v2):**
```json
{
  "title": "Write tests",
  "completed": true
}
```

### 5. Task Creation Requires `project_id`
Creating a new task via `POST /v2/tasks` now requires a `project_id`. Omitting it will result in an HTTP `422 Unprocessable Entity` error.

**Before (v1):**
```json
{
  "title": "New task title"
}
```

**After (v2):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Envelopes
The `GET /v2/tasks` list endpoint no longer returns a bare JSON array. It now returns a paginated envelope object. You must update your application code to extract the `items` array and use `next_cursor` for fetching subsequent pages.

**Before (v1):**
```json
[
  { 
    "id": 1, 
    "title": "Buy milk", 
    "done": false,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

**After (v2):**
```json
{
  "items": [
    { 
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", 
      "title": "Buy milk", 
      "completed": false, 
      "project_id": "proj_abc123",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Prepend `/v2` to all Zrb API endpoint paths in your client.
- [ ] Replace `X-Auth-Token` headers with `Authorization: Bearer <token>`.
- [ ] Update data models, interfaces, and database schemas to treat Task `id`s as UUID strings instead of integers.
- [ ] Rename all code references (models, JSON payloads, UI state) from `done` to `completed`.
- [ ] Ensure all `POST /v2/tasks` request payloads include a valid `project_id`.
- [ ] Update list endpoint consumption to extract `.items` from the response envelope and handle cursor-based pagination.

## Upgrade Command

```bash
zrb upgrade
```