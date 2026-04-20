# Zrb API v2 Migration Guide

Welcome to Zrb CLI and API v2. This release introduces projects, improved pagination, and stricter authentication. Several v1 fields and conventions have changed to support these improvements.

This guide outlines all breaking changes and provides a step-by-step checklist to upgrade your integration safely.

## Breaking Changes

### 1. Endpoint Prefix Updated
All endpoints are now versioned and must be prefixed with `/v2/`.

**Before:**
```http
GET /tasks
```

**After:**
```http
GET /v2/tasks
```

### 2. Authentication Header Changed
The custom authentication header has been replaced with the standard Bearer token scheme. Passing the old header will now return an HTTP 401.

**Before:**
```http
X-Auth-Token: <your_api_key>
```

**After:**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task `id` Type is now a UUID
Task IDs have migrated from auto-assigned integers to UUID strings.

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

### 4. `done` Field Renamed to `completed`
The boolean flag indicating task status has been renamed.

**Before:**
```json
{
  "title": "Updated title",
  "done": true
}
```

**After:**
```json
{
  "title": "Updated title",
  "completed": true
}
```

### 5. Task Creation Requires `project_id`
You can no longer create standalone tasks. Every `POST /v2/tasks` request must include a valid `project_id`, otherwise the API will return HTTP 422.

**Before:**
```json
{
  "title": "New task title"
}
```

**After:**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. List Endpoints are Paginated
Endpoints that return lists (like `GET /v2/tasks`) no longer return a bare array. They now return a paginated envelope. To fetch subsequent pages, pass the `next_cursor` value as a `?cursor=` query parameter.

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
    { "id": "a1b2c3d4...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123" }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist

Follow these steps to fully migrate your codebase to v2:

- [ ] Update all API request URLs to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token` headers with `Authorization: Bearer <token>`.
- [ ] Update your data models and database schemas to store task `id`s as UUID strings instead of integers.
- [ ] Refactor all read/write references of the `done` property to `completed`.
- [ ] Update task creation logic to retrieve and send a `project_id`.
- [ ] Modify response parsing for list endpoints to iterate over the `items` property rather than the root array.
- [ ] Implement cursor-based pagination logic using `next_cursor` for listing tasks.

## Upgrade Command

To update your local CLI environment to the new version, run:

```bash
npm install -g zrb@v2
```