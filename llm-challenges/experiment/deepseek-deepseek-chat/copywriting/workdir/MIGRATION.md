# Zrb CLI v1 to v2 Migration Guide

This guide helps experienced Zrb CLI developers migrate from v1 to v2. v2 introduces several breaking changes to improve scalability, security, and developer experience.

## Overview of Breaking Changes

1. **Endpoint Paths**: All endpoints now prefixed with `/v2/`
2. **Authentication**: Header changed from `X-Auth-Token` to Bearer token
3. **Task ID Type**: Changed from integer to UUID string
4. **Field Renaming**: `done` field renamed to `completed`
5. **Required Field**: Task creation now requires `project_id`
6. **Response Format**: List endpoints return paginated envelope instead of bare array

---

## 1. Endpoint Path Prefix

### Before (v1)
```http
GET /tasks
POST /tasks
GET /tasks/{id}
PUT /tasks/{id}
DELETE /tasks/{id}
```

### After (v2)
```http
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/{id}
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

**Impact**: All API calls must be updated to use the `/v2/` prefix.

---

## 2. Authentication Header

### Before (v1)
```http
X-Auth-Token: your_api_key_here
```

### After (v2)
```http
Authorization: Bearer your_api_token_here
```

**Note**: The v1 header will return HTTP 401 Unauthorized in v2.

---

## 3. Task ID Type Change

### Before (v1)
Task IDs were integers:
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2)
Task IDs are now UUID strings:
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Impact**: 
- All code that stores, compares, or manipulates task IDs must be updated
- URL paths for GET/PUT/DELETE operations must use UUID strings
- Database schemas storing task IDs need migration

---

## 4. Field Renaming: `done` → `completed`

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Impact**:
- Update all references to the `done` field in your code
- Update task creation/update requests to use `completed` instead of `done`

---

## 5. Required `project_id` Field

### Before (v1)
Task creation only required `title`:
```json
{
  "title": "New task"
}
```

### After (v2)
Task creation now requires both `title` and `project_id`:
```json
{
  "title": "New task",
  "project_id": "proj_abc123"
}
```

**Impact**: 
- All task creation requests must include a `project_id`
- You'll need to obtain project IDs before creating tasks
- Omitting `project_id` returns HTTP 422 Unprocessable Entity

---

## 6. Paginated Response Format

### Before (v1)
List endpoints returned a bare array:
```json
[
  {"id": 1, "title": "Task 1", "done": false, "created_at": "..."},
  {"id": 2, "title": "Task 2", "done": true, "created_at": "..."}
]
```

### After (v2)
List endpoints return a paginated envelope:
```json
{
  "items": [
    {"id": "uuid-1", "title": "Task 1", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "uuid-2", "title": "Task 2", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Impact**:
- Update code that parses list responses to access `items` array
- Implement pagination handling using `next_cursor`
- The default limit is 20 items per page (use `?limit=` to adjust)

---

## Complete Migration Example

### Before (v1)
```javascript
// Authentication
const headers = {
  'X-Auth-Token': 'your_api_key'
};

// List tasks
const response = await fetch('/tasks', { headers });
const tasks = await response.json(); // Direct array

// Create task
const newTask = await fetch('/tasks', {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'New task' })
});

// Update task (mark as done)
await fetch('/tasks/42', {
  method: 'PUT',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ done: true })
});
```

### After (v2)
```javascript
// Authentication
const headers = {
  'Authorization': 'Bearer your_api_token'
};

// List tasks (with pagination)
const response = await fetch('/v2/tasks?limit=50', { headers });
const result = await response.json();
const tasks = result.items; // Access items array
const nextCursor = result.next_cursor;

// Create task (requires project_id)
const newTask = await fetch('/v2/tasks', {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ 
    title: 'New task',
    project_id: 'proj_abc123'  // Required field
  })
});

// Update task (mark as completed)
await fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', {
  method: 'PUT',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ completed: true })  // Field renamed
});
```

---

## Step-by-Step Migration Checklist

### Phase 1: Preparation
- [ ] Review your codebase for all Zrb API calls
- [ ] Identify all stored task IDs (database, cache, local storage)
- [ ] Obtain project IDs for existing tasks
- [ ] Set up a testing environment with v2

### Phase 2: Authentication Update
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer`
- [ ] Update all API calls to use `/v2/` endpoint prefix
- [ ] Test authentication with v2 endpoints

### Phase 3: Data Model Updates
- [ ] Update task ID handling from integers to UUID strings
- [ ] Rename all references from `done` to `completed`
- [ ] Add `project_id` to all task creation requests
- [ ] Update database schemas if storing task data locally

### Phase 4: Response Handling
- [ ] Update list response parsing to use `result.items` instead of direct array
- [ ] Implement pagination logic using `next_cursor`
- [ ] Update error handling for new HTTP status codes (401, 422)

### Phase 5: Testing
- [ ] Test all CRUD operations with v2 endpoints
- [ ] Verify pagination works correctly
- [ ] Test error scenarios (missing project_id, invalid UUID)
- [ ] Run integration tests with your application

### Phase 6: Deployment
- [ ] Deploy changes to staging environment
- [ ] Monitor for any issues
- [ ] Deploy to production
- [ ] Update documentation for your team

---

## Upgrade Command

Once your code is migrated to support v2, update your Zrb CLI installation:

```bash
# Update to the latest v2 release
pip install --upgrade zrb==2.*

# Or using npm (if using Node.js client)
npm install @zrb/cli@latest
```

## Support

- **Migration Period**: v1 will be supported for 90 days after v2 release
- **Documentation**: Full v2 documentation available at [docs.zrb.dev/v2](https://docs.zrb.dev/v2)
- **Support Channel**: Join our [Discord community](https://discord.gg/zrb) for migration assistance

## Need Help?

If you encounter issues during migration:
1. Check the [v2 API reference](https://docs.zrb.dev/v2/api)
2. Review the [common migration issues](https://docs.zrb.dev/v2/migration-faq)
3. Contact support at support@zrb.dev

---

*Last updated: April 2026*