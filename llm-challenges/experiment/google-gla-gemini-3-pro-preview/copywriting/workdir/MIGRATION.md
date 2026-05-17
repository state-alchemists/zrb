# Zrb Task API v2 Migration Guide

Welcome to the Zrb Task API v2. This release introduces support for projects, improved pagination, and stricter authentication. 

Because v2 includes structural changes to endpoints and data types, this guide outlines every breaking change and provides a step-by-step checklist to help you transition your existing v1 integrations.

---

## Breaking Changes

### 1. Endpoint Prefix Updated
All endpoints are now strictly versioned and prefixed with `/v2/`. 

**Before (v1)**
```http
GET /tasks
```

**After (v2)**
```http
GET /v2/tasks
```

### 2. Authentication Header Changed
The custom authentication header has been replaced with the standard OAuth2 Bearer token format. Using the old header will now result in an `HTTP 401 Unauthorized` error.

**Before (v1)**
```http
X-Auth-Token: your_api_token
```

**After (v2)**
```http
Authorization: Bearer your_api_token
```

### 3. Task IDs are now UUID Strings
Task identifiers have been migrated from auto-incrementing integers to UUID strings. Update your database schemas and type definitions accordingly.

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

### 4. The `done` Field is Renamed to `completed`
To standardise terminology, the boolean field indicating task completion is now `completed`. This affects both task creation/updates and response parsing.

**Before (v1)**
```json
{
  "title": "Write tests",
  "done": true
}
```

**After (v2)**
```json
{
  "title": "Write tests",
  "completed": true
}
```

### 5. `project_id` is Required for Task Creation
With the introduction of project scoping, you can no longer create orphaned tasks. Every `POST /v2/tasks` request must include a valid `project_id`. Omitting it will result in an `HTTP 422 Unprocessable Entity` error.

**Before (v1)**
```json
// POST /tasks
{
  "title": "New task title"
}
```

**After (v2)**
```json
// POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. List Responses use a Paginated Envelope
List endpoints no longer return a bare array. They now return a pagination envelope containing `items`, `total`, and a `next_cursor` for fetching subsequent pages.

**Before (v1)**
```json
[
  { "id": 1, "title": "Buy milk", "done": false }
]
```

**After (v2)**
```json
{
  "items": [
    { "id": "uuid-...", "title": "Buy milk", "completed": false, "project_id": "proj_123" }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist

Follow these steps to upgrade your application to v2:

- [ ] **Update Base URLs:** Append `/v2` to your API base URL for all task-related network calls.
- [ ] **Swap Auth Headers:** Replace the `X-Auth-Token` header with `Authorization: Bearer <token>` in your HTTP client interceptors or configuration.
- [ ] **Update Type Definitions:** Change the `id` field on the Task model from `integer` to `string` (UUID).
- [ ] **Rename State Variables:** Perform a project-wide find-and-replace for the task `done` property, renaming it to `completed`.
- [ ] **Provide Project Context:** Update your task creation logic to fetch or inject a valid `project_id` into the request body.
- [ ] **Update Response Parsers:** Modify any logic that parses `GET /v2/tasks` to map over `response.data.items` instead of iterating over `response.data` directly.

---

## Upgrade Command

To update your Zrb CLI to the latest v2 release, run:

```bash
zrb upgrade
```