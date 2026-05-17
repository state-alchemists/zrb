# Zrb CLI v2 Migration Guide

Zrb v2 introduces projects, improved pagination, and stricter authentication. This guide outlines the breaking changes from the v1 API and how to update your integration to support v2.

## Breaking Changes

### 1. API Endpoint Prefix

All API endpoints are now prefixed with `/v2/`.

**Before (v1)**
```http
GET /tasks
```

**After (v2)**
```http
GET /v2/tasks
```

### 2. Authentication Header

The authentication header has changed to the standard Bearer token format. Requests using the old `X-Auth-Token` header will return an HTTP 401 Unauthorized error.

**Before (v1)**
```http
X-Auth-Token: <your_api_key>
```

**After (v2)**
```http
Authorization: Bearer <your_api_key>
```

### 3. Task ID Format

Task identifiers have been migrated from auto-incrementing integers to UUID strings. Ensure your database schemas, type definitions, and route parameters are updated to handle string IDs.

**Before (v1)**
```json
{
  "id": 42
}
```

**After (v2)**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 4. Renamed Status Field

The boolean field representing a task's status has been renamed from `done` to `completed` across all read and write operations.

**Before (v1)**
```json
{
  "title": "Write tests",
  "done": false
}
```

**After (v2)**
```json
{
  "title": "Write tests",
  "completed": false
}
```

### 5. Task Creation Requires a Project ID

Creating a new task now requires a `project_id`. Omitting this field will result in an HTTP 422 Unprocessable Entity error.

**Before (v1)**
```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2)**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Responses

List endpoints no longer return a bare array. They now return a paginated JSON envelope containing `items`, `total`, and a `next_cursor` for fetching subsequent pages.

**Before (v1)**
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

**After (v2)**
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

- [ ] Update all API request paths to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` headers with `Authorization: Bearer <token>`.
- [ ] Update database schemas, type definitions, and variable parsing to treat `id` as a UUID string instead of an integer.
- [ ] Rename references to the `done` field to `completed` in your data models, UI components, and API requests.
- [ ] Inject a valid `project_id` into all `POST /v2/tasks` payloads.
- [ ] Refactor list endpoint data fetching to extract the `items` array from the new paginated response envelope.
- [ ] Implement cursor-based pagination using the `next_cursor` field where applicable.

## Upgrade Command

To update your Zrb CLI to the latest v2 release, run:

```bash
npm install -g zrb@2
```