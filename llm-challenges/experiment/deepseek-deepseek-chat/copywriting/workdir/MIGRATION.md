# Zrb CLI v1 to v2 Migration Guide

This guide helps experienced Zrb CLI developers migrate from v1 to v2. v2 introduces several breaking changes to improve security, scalability, and developer experience.

## Overview of Breaking Changes

1. **Endpoint Paths**: All endpoints now prefixed with `/v2/`
2. **Authentication**: Header changed from `X-Auth-Token` to Bearer token
3. **Task ID Type**: Changed from integer to UUID string
4. **Task Status Field**: `done` renamed to `completed`
5. **Task Creation**: Now requires `project_id` field
6. **List Responses**: Return paginated envelope instead of bare array

## Detailed Migration Steps

### 1. Update Endpoint Paths

All API endpoints have moved from `/tasks` to `/v2/tasks`.

**Before (v1):**
```javascript
// List tasks
fetch('/tasks')

// Get specific task
fetch('/tasks/42')

// Create task
fetch('/tasks', { method: 'POST' })

// Update task
fetch('/tasks/42', { method: 'PUT' })

// Delete task
fetch('/tasks/42', { method: 'DELETE' })
```

**After (v2):**
```javascript
// List tasks
fetch('/v2/tasks')

// Get specific task
fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890')

// Create task
fetch('/v2/tasks', { method: 'POST' })

// Update task
fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', { method: 'PUT' })

// Delete task
fetch('/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890', { method: 'DELETE' })
```

### 2. Update Authentication Header

The authentication mechanism has changed from a custom header to standard Bearer token format.

**Before (v1):**
```javascript
const headers = {
  'X-Auth-Token': 'your_api_key_here'
};
```

**After (v2):**
```javascript
const headers = {
  'Authorization': 'Bearer your_api_token_here'
};
```

**Note:** Requests using the old `X-Auth-Token` header will receive HTTP 401 Unauthorized responses.

### 3. Handle Task ID Type Change

Task IDs are now UUID strings instead of integers. Update all code that stores, compares, or parses task IDs.

**Before (v1):**
```javascript
// Storing ID
const taskId = 42; // integer

// Comparing IDs
if (task.id === 42) { ... }

// Parsing from URL
const pathParts = url.split('/');
const taskId = parseInt(pathParts[pathParts.length - 1], 10);
```

**After (v2):**
```javascript
// Storing ID
const taskId = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'; // UUID string

// Comparing IDs
if (task.id === 'a1b2c3d4-e5f6-7890-abcd-ef1234567890') { ... }

// Parsing from URL (no parseInt needed)
const pathParts = url.split('/');
const taskId = pathParts[pathParts.length - 1];
```

### 4. Rename Task Status Field

The boolean field indicating task completion has been renamed from `done` to `completed`.

**Before (v1):**
```javascript
// Reading status
const isDone = task.done;

// Updating status
const updateData = {
  done: true
};

// Filtering tasks
const completedTasks = tasks.filter(task => task.done);
```

**After (v2):**
```javascript
// Reading status
const isCompleted = task.completed;

// Updating status
const updateData = {
  completed: true
};

// Filtering tasks
const completedTasks = tasks.filter(task => task.completed);
```

### 5. Add Project ID to Task Creation

Task creation now requires a `project_id` field. This is a breaking change for all `POST /tasks` requests.

**Before (v1):**
```javascript
const taskData = {
  title: 'New task title'
  // No project_id required
};
```

**After (v2):**
```javascript
const taskData = {
  title: 'New task title',
  project_id: 'proj_abc123' // REQUIRED field
};
```

**Note:** Omitting `project_id` will result in HTTP 422 Unprocessable Entity response.

### 6. Handle Paginated List Responses

List endpoints now return a paginated envelope instead of a bare array. Update your response handling accordingly.

**Before (v1):**
```javascript
// Response handling
fetch('/tasks')
  .then(response => response.json())
  .then(tasks => {
    // tasks is an array
    tasks.forEach(task => {
      console.log(task.title);
    });
  });
```

**After (v2):**
```javascript
// Response handling
fetch('/v2/tasks')
  .then(response => response.json())
  .then(response => {
    // response is an envelope with items array
    const tasks = response.items;
    const total = response.total;
    const nextCursor = response.next_cursor;
    
    tasks.forEach(task => {
      console.log(task.title);
    });
    
    // Pagination example
    if (nextCursor) {
      fetch(`/v2/tasks?cursor=${nextCursor}`)
        .then(/* handle next page */);
    }
  });
```

## Migration Checklist

Follow these steps to migrate your application from v1 to v2:

### Phase 1: Preparation
- [ ] Review your codebase for all Zrb API calls
- [ ] Identify all instances where task IDs are stored or manipulated
- [ ] Locate all authentication header configurations
- [ ] Find all task status checks and updates
- [ ] Document all task creation endpoints
- [ ] Note all list response handling code

### Phase 2: Code Updates
- [ ] Update all endpoint URLs from `/tasks` to `/v2/tasks`
- [ ] Change authentication headers from `X-Auth-Token` to `Authorization: Bearer`
- [ ] Convert all task ID handling from integers to UUID strings
- [ ] Rename all `done` field references to `completed`
- [ ] Add `project_id` to all task creation requests
- [ ] Update list response handling to use paginated envelope (`response.items` instead of direct array)

### Phase 3: Testing
- [ ] Test authentication with new Bearer token format
- [ ] Verify task creation with required `project_id`
- [ ] Test task retrieval with UUID IDs
- [ ] Validate task status updates using `completed` field
- [ ] Test pagination handling for list endpoints
- [ ] Run integration tests for all API workflows

### Phase 4: Deployment
- [ ] Deploy to staging environment first
- [ ] Monitor for 401 errors (old auth header)
- [ ] Monitor for 422 errors (missing `project_id`)
- [ ] Monitor for 404 errors (integer IDs vs UUIDs)
- [ ] Update API documentation for your consumers
- [ ] Communicate changes to your team/users

## Upgrade Command

To upgrade your Zrb CLI installation:

```bash
# Using npm
npm install -g zrb@latest

# Using yarn
yarn global add zrb@latest

# Using pip
pip install --upgrade zrb

# Verify the upgrade
zrb --version
```

## Support

If you encounter issues during migration:
1. Check the [Zrb v2 documentation](https://docs.zrb.dev/v2/)
2. Review error responses for specific guidance
3. Contact support at support@zrb.dev
4. Join our community Discord for peer assistance

## Rollback Plan

If you need to rollback to v1 temporarily:

1. Reinstall v1: `npm install -g zrb@1.x`
2. Revert your code changes
3. Use v1 endpoints and authentication
4. Contact support to discuss migration blockers

---

*Last updated: April 2026*