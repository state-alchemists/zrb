# Zrb API v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in Zrb API v2 and provides a step-by-step process for migrating your application from v1.

## Summary of Breaking Changes

- **API Path Versioning**: All endpoints are now prefixed with `/v2`.
- **Authentication**: The `X-Auth-Token` header is replaced by `Authorization: Bearer <token>`.
- **Task ID Type**: The `id` field for tasks is now a UUID string instead of an integer.
- **Field Rename**: The `done` field in the Task object has been renamed to `completed`.
- **Paginated Responses**: All list endpoints now return a structured envelope with items and pagination details, instead of a bare array.
- **Project ID Required**: Creating a task now requires a `project_id`.

---

## Detailed Breaking Changes

### 1. API Endpoint Path

All v1 endpoints have been moved under the `/v2/` path prefix.

**Before (v1):**
```
GET /tasks
POST /tasks
GET /tasks/{id}
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/{id}
```

### 2. Authentication Header

Authentication now uses the standard `Authorization` header with a Bearer token.

**Before (v1):**
```
curl -H "X-Auth-Token: your_api_key" https://api.zrb.com/tasks
```

**After (v2):**
```
curl -H "Authorization: Bearer your_api_token" https://api.zrb.com/v2/tasks
```

### 3. Task ID Data Type

The `id` field for tasks has changed from an integer to a UUID string. Update any database columns or variables that store this ID.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Ship v1",
  "done": true,
  "created_at": "..."
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Launch v2",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "..."
}
```

### 4. Field Rename: `done` to `completed`

The boolean field indicating a task's status is now `completed`.

**Before (v1):**
```javascript
// Updating a task
const payload = { done: true };
fetch(`/tasks/${taskId}`, {
  method: 'PUT',
  body: JSON.stringify(payload)
});

// Reading a task
if (task.done) {
  // ...
}
```

**After (v2):**
```javascript
// Updating a task
const payload = { completed: true };
fetch(`/v2/tasks/${taskId}`, {
  method: 'PUT',
  body: JSON.stringify(payload)
});

// Reading a task
if (task.completed) {
  // ...
}
```

### 5. Paginated List Responses

The `GET /tasks` endpoint no longer returns a bare array. It now returns a paginated object containing the items and pagination metadata.

**Before (v1):**
```javascript
// Request
fetch('/tasks')
  .then(res => res.json())
  .then(tasks => {
    // tasks is an array: [{...}, {...}]
    console.log(`Found ${tasks.length} tasks.`);
  });
```

**After (v2):**
```javascript
// Request
fetch('/v2/tasks')
  .then(res => res.json())
  .then(response => {
    // response is an object: { items: [...], total: 42, next_cursor: "..." }
    const tasks = response.items;
    console.log(`Found ${tasks.length} tasks on this page.`);
    
    // To fetch the next page:
    if (response.next_cursor) {
      fetch(`/v2/tasks?cursor=${response.next_cursor}`);
    }
  });
```

### 6. Required `project_id` for Task Creation

When creating a new task, the `project_id` field is now mandatory.

**Before (v1):**
```javascript
// POST /tasks
const payload = {
  title: "My new task"
};
```

**After (v2):**
```javascript
// POST /v2/tasks
const payload = {
  title: "My new task",
  project_id: "proj_abc123" // This is now required
};
```

---

## Migration Checklist

Follow these steps to migrate your application to v2:

- [ ] **Update Base URL**: Add the `/v2` prefix to all API endpoint URLs.
- [ ] **Update Authentication**: Change your HTTP client to send `Authorization: Bearer <token>` instead of `X-Auth-Token`.
- [ ] **Update ID Handling**: Change any variables, function parameters, or database columns that handle Task IDs from `integer` to `string`/`UUID`.
- [ ] **Update Field References**: Rename all instances of the `done` field to `completed` in your application code.
- [ ] **Update List Handling**: Modify code that calls `GET /tasks` to handle the new paginated response structure (access the `items` property).
- [ ] **Update Task Creation**: Add the required `project_id` field to all `POST /v2/tasks` requests.

## Upgrade Command

To upgrade your Zrb CLI to the latest version, run:

```bash
npm install -g zrb-cli@latest
```
