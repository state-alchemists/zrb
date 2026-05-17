# Migrating from Zrb CLI v1 to v2

This guide helps you migrate your applications from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication. Several v1 fields and conventions have changed.

## Quick Summary of Breaking Changes

| Change | v1 | v2 |
|--------|----|----|
| Endpoint prefix | `/tasks` | `/v2/tasks` |
| Auth header | `X-Auth-Token` | `Authorization: Bearer` |
| Task ID type | Integer | UUID string |
| Task status field | `done` | `completed` |
| Task creation | Optional fields | Requires `project_id` |
| List response | Bare array | Paginated envelope |

---

## Breaking Change 1: Endpoint Prefix

All endpoints now require a `/v2/` prefix.

### Before (v1)
```bash
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

### After (v2)
```bash
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Migration Steps
1. Update all endpoint URLs in your codebase to include `/v2/` prefix
2. Update any hardcoded API paths in configuration files
3. Test each endpoint to ensure routing works correctly

---

## Breaking Change 2: Authentication Header

The authentication header has changed from `X-Auth-Token` to Bearer token format.

### Before (v1)
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.io/tasks
```

```javascript
// JavaScript/Node.js
headers: {
  'X-Auth-Token': 'your_api_key'
}
```

```python
# Python
headers = {
  'X-Auth-Token': 'your_api_key'
}
```

### After (v2)
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.io/v2/tasks
```

```javascript
// JavaScript/Node.js
headers: {
  'Authorization': 'Bearer your_api_token'
}
```

```python
# Python
headers = {
  'Authorization': 'Bearer your_api_token'
}
```

### Migration Steps
1. Locate all places where `X-Auth-Token` is set
2. Replace with `Authorization: Bearer <token>` format
3. Verify your API token works with the new header format
4. Requests using the old header will receive HTTP 401

---

## Breaking Change 3: Task ID Type

Task IDs have changed from integer to UUID strings. This affects all endpoints that reference a task by ID.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```bash
GET /tasks/42
PUT /tasks/42
DELETE /tasks/42
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

```bash
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Migration Steps
1. Update your data models to store UUID strings instead of integers
2. Change any ID validation logic to accept UUID format
3. Update database schemas if you're persisting task IDs
4. Migrate existing integer IDs to UUIDs (see data migration section below)

---

## Breaking Change 4: Task Status Field Rename

The `done` field has been renamed to `completed`. This affects task objects in responses and request bodies.

### Before (v1)
```json
// Response
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}

// Update request
PUT /tasks/42
{
  "title": "Updated title",
  "done": true
}
```

### After (v2)
```json
// Response
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}

// Update request
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
{
  "title": "Updated title",
  "completed": true
}
```

### Migration Steps
1. Find all references to `done` field in your codebase
2. Replace with `completed`
3. Update any UI labels or display logic
4. Update form field names in your frontend
5. Update any serialization/deserialization logic

---

## Breaking Change 5: Task Creation Requires Project ID

Creating a task now requires a `project_id` field. Omitting it returns HTTP 422.

### Before (v1)
```json
POST /tasks
{
  "title": "New task title"
}
```

### After (v2)
```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### Migration Steps
1. Identify all places where tasks are created
2. Add `project_id` to each task creation request
3. Ensure you have valid project IDs available (use the projects API to list/create projects)
4. Update any forms or UI to include project selection
5. Handle HTTP 422 errors gracefully if `project_id` is missing

---

## Breaking Change 6: List Response Format

List endpoints now return a paginated envelope instead of a bare array.

### Before (v1)
```json
GET /tasks

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
// JavaScript/Node.js
const tasks = await fetch('/tasks').then(r => r.json());
tasks.forEach(task => console.log(task.title));
```

### After (v2)
```json
GET /v2/tasks

{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-f6g7-8901-bcde-f12345678901", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// JavaScript/Node.js
const response = await fetch('/v2/tasks').then(r => r.json());
const tasks = response.items;
tasks.forEach(task => console.log(task.title));

// Pagination
if (response.next_cursor) {
  const nextPage = await fetch(`/v2/tasks?cursor=${response.next_cursor}`).then(r => r.json());
}
```

### Migration Steps
1. Update all list endpoint response handling to access `items` array
2. Add pagination logic using `next_cursor` and `total` fields
3. Update any code that expects a bare array directly
4. Consider implementing automatic pagination for large result sets
5. Use the `limit` query parameter to control page size (default: 20)

---

## Complete Migration Checklist

Use this checklist to track your migration progress:

### Authentication & Endpoints
- [ ] Update all endpoint URLs to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer`
- [ ] Test authentication with new header format

### Data Model Changes
- [ ] Update task ID storage from integer to UUID string
- [ ] Update ID validation logic for UUID format
- [ ] Rename `done` field to `completed` in data models
- [ ] Add `project_id` field to task data models
- [ ] Update database schema if persisting task data

### API Integration Updates
- [ ] Update GET `/v2/tasks` response handling to use `items` array
- [ ] Implement pagination using `next_cursor` and `total`
- [ ] Update POST `/v2/tasks` to include `project_id`
- [ ] Update PUT `/v2/tasks/{id}` to use `completed` field
- [ ] Update DELETE `/v2/tasks/{id}` to use UUID IDs

### Frontend/UI Updates
- [ ] Update forms to include project selection
- [ ] Update UI labels from "done" to "completed"
- [ ] Update pagination controls for new format
- [ ] Update any ID display logic for UUID format

### Testing
- [ ] Test all CRUD operations (Create, Read, Update, Delete)
- [ ] Test pagination with cursor-based navigation
- [ ] Test error handling for missing `project_id`
- [ ] Test authentication with new header format
- [ ] Run integration tests with v2 endpoints

### Data Migration (if applicable)
- [ ] Back up existing data
- [ ] Migrate integer IDs to UUIDs
- [ ] Assign existing tasks to projects
- [ ] Verify data integrity after migration

---

## Upgrade Command

To upgrade your Zrb CLI to v2, run:

```bash
npm install -g @zrb/cli@latest
# or
yarn global add @zrb/cli@latest
# or
pip install --upgrade zrb-cli
```

After upgrading, verify your version:

```bash
zrb --version
# Should output: zrb-cli v2.x.x
```

---

## Need Help?

- Review the [v2 API specification](./v2_spec.md) for complete endpoint details
- Check the [v1 API specification](./v1_spec.md) for reference during migration
- Open an issue on GitHub if you encounter problems
- Join our Discord community for real-time support