# Zrb Task API v2 Migration Guide

Welcome to Zrb CLI and API v2. This release introduces robust project grouping, improved pagination, and stricter authentication. 

Because of these structural improvements, v2 includes several breaking changes from v1. This guide covers every breaking change and provides a step-by-step checklist to help you upgrade your integrations.

---

## Breaking Changes

### 1. Endpoint Path Prefix

All endpoints have been moved under the `/v2/` prefix.

**Before (v1):**
```http
GET /tasks
```

**After (v2):**
```http
GET /v2/tasks
```

### 2. Authentication Header

The authentication method has changed from a custom `X-Auth-Token` header to the standard `Authorization: Bearer` token pattern. Using the old header will now result in an HTTP `401 Unauthorized` error.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_key>
```

### 3. Task ID Data Type

Task IDs are now UUID strings instead of auto-incrementing integers. You must update your database schemas or type definitions to expect string UUIDs.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

### 4. Renamed Field: `done` to `completed`

The boolean field representing task completion has been renamed. This affects both the task representation returned by the API and the payload used in `PUT /v2/tasks/{id}`.

**Before (v1):**
```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2):**
```json
{
  "title": "Updated title",
  "completed": true
}
```

### 5. Required `project_id` on Creation

Tasks can no longer exist globally. When creating a task via `POST /v2/tasks`, you must now provide a valid `project_id`. Omitting it will result in an HTTP `422 Unprocessable Entity` error.

**Before (v1):**
```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. Paginated List Responses

The `GET /v2/tasks` endpoint no longer returns a bare JSON array. It now returns a paginated envelope object containing `items`, `total`, and a `next_cursor` for fetching subsequent pages.

**Before (v1):**
```json
[
  {
    "id": 1,
    "title": "Buy milk",
    "done": false
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
      "project_id": "proj_abc123"
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist

Follow these steps to safely migrate your integration from v1 to v2:

- [ ] **Update Auth Headers**: Replace all `X-Auth-Token: <key>` headers with `Authorization: Bearer <key>`.
- [ ] **Update Base URLs**: Prepend `/v2` to all task endpoints (e.g., `/tasks` becomes `/v2/tasks`).
- [ ] **Adjust Data Types**: Ensure your local database, ORM, and types treat Task `id` as a UUID string, not an integer.
- [ ] **Rename Fields**: Search and replace the `done` property with `completed` in both your request payloads and response parsing logic.
- [ ] **Require Projects**: Update your task creation logic (`POST`) to always include a `project_id`.
- [ ] **Handle Pagination**: Refactor your `GET /v2/tasks` list parsing to read from the `.items` property rather than expecting a root-level array. Implement cursor-based pagination if you fetch large numbers of tasks.

---

## Upgrade Command

Run the following command to upgrade your CLI to v2:

```bash
zrb upgrade
```