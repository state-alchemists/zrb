# Migrating from Zrb API v1 to v2

The Zrb API v2 introduces projects, standardized pagination, and stricter authentication. This guide outlines the breaking changes from v1 and provides the necessary steps to upgrade your existing integrations.

## Breaking Changes

### 1. Base URL and API Prefix
All endpoint paths now require a `/v2/` prefix. 

**Before (v1):**
```http
GET /tasks
```

**After (v2):**
```http
GET /v2/tasks
```

### 2. Authentication Header
The custom `X-Auth-Token` header has been replaced with the standard OAuth Bearer token format. Legacy requests will be rejected with an HTTP 401 error.

**Before (v1):**
```http
X-Auth-Token: <your_api_token>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

### 3. Task Model: ID and Status
The Task data model contains two breaking updates:
- The `id` field is now a **UUID string** instead of an integer.
- The `done` boolean field has been renamed to `completed`.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": true
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true,
  "project_id": "proj_abc123"
}
```

### 4. Task Creation Requires a Project
Floating tasks are no longer supported. The `POST /v2/tasks` endpoint now requires a `project_id`. Omitting this field returns an HTTP 422 error.

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

### 5. Paginated List Endpoints
The `GET /v2/tasks` endpoint no longer returns a bare JSON array. Responses are now wrapped in a paginated envelope containing `items`, `total`, and a `next_cursor` for fetching subsequent pages.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."}
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
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

Follow these steps to safely transition your codebase:

- [ ] Update all API request paths to prefix endpoints with `/v2/`.
- [ ] Change your HTTP client's authentication header from `X-Auth-Token` to `Authorization: Bearer`.
- [ ] Migrate your local database schemas and type definitions to store Task `id` fields as UUID strings rather than integers.
- [ ] Find and rename all codebase references from `done` to `completed` for Task objects.
- [ ] Update task creation payloads (`POST /v2/tasks`) to include a valid `project_id`.
- [ ] Refactor array parsing logic on list endpoints to map over `response.items` instead of assuming the root response is an array.
- [ ] Implement cursor-based pagination utilizing `response.next_cursor` where needed.

## Upgrade

Run the following command to upgrade your Zrb CLI to the new release:

```bash
zrb upgrade
```