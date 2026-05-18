# Zrb v2 Migration Guide

Zrb v2 introduces projects, improved pagination, and a more secure authentication method. This guide helps you migrate your existing v1 integrations to the new API.

## Global Changes

### 1. Endpoint Prefixing
All API endpoints are now prefixed with `/v2/`.

**Before:**
`GET /tasks`

**After:**
`GET /v2/tasks`

### 2. Authentication Header
The `X-Auth-Token` header has been replaced with the standard `Authorization: Bearer` scheme.

**Before:**
```http
X-Auth-Token: your_api_key
```

**After:**
```http
Authorization: Bearer your_api_token
```

## Data Model Changes

### 3. Task ID Format
Task identifiers have changed from integers to UUID strings. Ensure your local database schemas or variables are updated to handle 36-character strings.

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

### 4. Field Rename: `done` to `completed`
The `done` field on the Task object has been renamed to `completed`.

**Before:**
```json
{
  "title": "Fix bug",
  "done": true
}
```

**After:**
```json
{
  "title": "Fix bug",
  "completed": true
}
```

## Endpoint Changes

### 5. Task Creation Requirements
Creating a task now requires a `project_id`.

**Before:**
```json
POST /tasks
{
  "title": "New Task"
}
```

**After:**
```json
POST /v2/tasks
{
  "title": "New Task",
  "project_id": "proj_abc123"
}
```

### 6. List Response Envelope
List endpoints no longer return a bare array. They now return a paginated object containing an `items` array and metadata.

**Before:**
```json
[
  {"id": "...", "title": "..."}
]
```

**After:**
```json
{
  "items": [
    {"id": "...", "title": "..."}
  ],
  "total": 1,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

- [ ] Update all API base URLs to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`.
- [ ] Update Task data models to use `completed` instead of `done`.
- [ ] Update Task ID types to support UUID strings.
- [ ] Refactor list processing logic to handle the new paginated envelope.
- [ ] Ensure all `POST /v2/tasks` calls include a valid `project_id`.

## Upgrade Command

To update your local Zrb CLI to the latest version, run:

```bash
zrb update --v2
```
