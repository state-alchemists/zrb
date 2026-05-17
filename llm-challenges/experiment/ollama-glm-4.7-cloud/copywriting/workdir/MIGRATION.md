# Migrating from Zrb CLI v1 to v2

This guide helps you migrate your code from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication. All v1 endpoints remain functional until the deprecation deadline, but you should migrate as soon as possible.

## Breaking Changes Summary

1. All endpoints now prefixed with `/v2/`
2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer`
3. Task `id` type changed from integer to UUID string
4. Task field `done` renamed to `completed`
5. Task creation now requires `project_id`
6. List endpoints return paginated envelope instead of bare array

---

## 1. Update Endpoint Paths

All API endpoints now require the `/v2/` prefix.

**Before (v1):**
```bash
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**
```bash
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Update Authentication Header

The authentication header changed from a custom header to the standard Bearer token format.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.io/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.io/v2/tasks
```

**Code example (JavaScript):**

```javascript
// v1
const headers = {
  'X-Auth-Token': apiKey
};

// v2
const headers = {
  'Authorization': `Bearer ${apiToken}`
};
```

---

## 3. Update Task ID Handling

Task IDs changed from integers to UUID strings. Update any code that stores, compares, or parses task IDs.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Code example (Python):**

```python
# v1
task_id = 42
url = f"https://api.zrb.io/tasks/{task_id}"

# v2
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
url = f"https://api.zrb.io/v2/tasks/{task_id}"
```

---

## 4. Rename `done` Field to `completed`

The task status field changed from `done` to `completed`. Update all references in your code.

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

**Code example (JavaScript):**

```javascript
// v1
const updatePayload = {
  title: "Updated title",
  done: true
};

// v2
const updatePayload = {
  title: "Updated title",
  completed: true
};
```

---

## 5. Add `project_id` to Task Creation

Creating a task now requires a `project_id`. You must obtain a valid project ID before creating tasks.

**Before (v1):**
```bash
POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**
```bash
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Code example (Python):**

```python
# v1
response = requests.post(
  "https://api.zrb.io/tasks",
  json={"title": "New task title"},
  headers={"X-Auth-Token": api_key}
)

# v2
response = requests.post(
  "https://api.zrb.io/v2/tasks",
  json={
    "title": "New task title",
    "project_id": "proj_abc123"
  },
  headers={"Authorization": f"Bearer {api_token}"}
)
```

---

## 6. Handle Paginated List Responses

List endpoints now return a paginated envelope instead of a bare array. Update your code to extract items from the envelope and handle pagination.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-f6g7-8901-bcde-f12345678901", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Code example (JavaScript):**

```javascript
// v1
const response = await fetch('https://api.zrb.io/tasks', {
  headers: { 'X-Auth-Token': apiKey }
});
const tasks = await response.json();

// v2
const response = await fetch('https://api.zrb.io/v2/tasks', {
  headers: { 'Authorization': `Bearer ${apiToken}` }
});
const data = await response.json();
const tasks = data.items;
const total = data.total;
const nextCursor = data.next_cursor;

// Fetch next page
if (nextCursor) {
  const nextPage = await fetch(`https://api.zrb.io/v2/tasks?cursor=${nextCursor}`, {
    headers: { 'Authorization': `Bearer ${apiToken}` }
  });
}
```

---

## Migration Checklist

Use this checklist to ensure you've addressed all breaking changes:

- [ ] Update all endpoint URLs to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer` header
- [ ] Update database schema or storage to use UUID strings for task IDs
- [ ] Rename all `done` field references to `completed`
- [ ] Add `project_id` to all task creation requests
- [ ] Update list response handling to extract `items` from paginated envelope
- [ ] Implement pagination logic using `next_cursor` and `total` fields
- [ ] Update any type definitions or interfaces to reflect new field names and types
- [ ] Test all CRUD operations (create, read, update, delete)
- [ ] Verify pagination works correctly for large datasets
- [ ] Update error handling for 401 (auth) and 422 (validation) responses

---

## Upgrade Command

To upgrade your Zrb CLI installation to v2:

```bash
npm install -g @zrb/cli@latest
# or
yarn global add @zrb/cli@latest
# or
brew upgrade zrb
```

After upgrading, verify your installation:

```bash
zrb --version
# Should output: zrb v2.x.x
```

---

## Need Help?

- Review the [v2 API Reference](./v2_spec.md) for complete endpoint documentation
- Check the [v1 API Reference](./v1_spec.md) to compare with your current implementation
- Open an issue on GitHub if you encounter migration problems