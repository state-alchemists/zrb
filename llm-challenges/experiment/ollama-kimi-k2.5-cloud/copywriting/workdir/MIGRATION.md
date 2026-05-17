# Migrating from Zrb CLI v1 to v2

This guide helps you migrate your codebase from Zrb CLI v1 to v2. v2 introduces projects, improved pagination, and stricter authentication. All breaking changes are listed below with before/after code examples.

## Breaking Changes

### 1. Base URL Path Prefix

All endpoints are now prefixed with `/v2/`.

**Before (v1):**
```bash
curl https://api.zrb.io/tasks
curl https://api.zrb.io/tasks/42
```

**After (v2):**
```bash
curl https://api.zrb.io/v2/tasks
curl https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication Header Changed

The `X-Auth-Token` header is deprecated. Use Bearer token format instead. Requests with the old header will receive HTTP 401.

**Before (v1):**
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.io/tasks
```

```javascript
// JavaScript
fetch('/tasks', {
  headers: { 'X-Auth-Token': apiKey }
});
```

```python
# Python
requests.get('/tasks', headers={'X-Auth-Token': api_key})
```

**After (v2):**
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.io/v2/tasks
```

```javascript
// JavaScript
fetch('/v2/tasks', {
  headers: { 'Authorization': `Bearer ${apiToken}` }
});
```

```python
# Python
requests.get('/v2/tasks', headers={'Authorization': f'Bearer {api_token}'})
```

---

### 3. Task ID Changed from Integer to UUID

Task IDs are now UUID strings. Update any code that expects integer IDs or performs ID arithmetic.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

```javascript
// JavaScript — parsing as integer
const taskId = parseInt(response.id);
```

```python
# Python — expecting integer
task_id: int = task["id"]
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

```javascript
// JavaScript — UUID is a string
const taskId = response.id; // "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

```python
# Python — UUID as string
task_id: str = task["id"]  # "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

---

### 4. Field Renamed: `done` → `completed`

The task status field has been renamed. Update all references in request bodies and response handling.

**Before (v1):**
```json
{
  "title": "Ship feature",
  "done": true
}
```

```javascript
// JavaScript
const isDone = task.done;
await updateTask(id, { done: true });
```

```python
# Python
is_done = task["done"]
update_task(id, done=True)
```

**After (v2):**
```json
{
  "title": "Ship feature",
  "completed": true
}
```

```javascript
// JavaScript
const isCompleted = task.completed;
await updateTask(id, { completed: true });
```

```python
# Python
is_completed = task["completed"]
update_task(id, completed=True)
```

---

### 5. Task Creation Requires `project_id`

Creating a task now requires a `project_id` field. Omitting it returns HTTP 422.

**Before (v1):**
```bash
curl -X POST https://api.zrb.io/tasks \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: <key>" \
  -d '{"title": "New task"}'
```

```javascript
// JavaScript
await fetch('/tasks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-Auth-Token': apiKey },
  body: JSON.stringify({ title: 'New task' })
});
```

```python
# Python
requests.post('/tasks', json={"title": "New task"})
```

**After (v2):**
```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

```javascript
// JavaScript
await fetch('/v2/tasks', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json', 
    'Authorization': `Bearer ${apiToken}` 
  },
  body: JSON.stringify({ title: 'New task', project_id: 'proj_abc123' })
});
```

```python
# Python
requests.post(
    '/v2/tasks', 
    headers={'Authorization': f'Bearer {api_token}'},
    json={"title": "New task", "project_id": "proj_abc123"}
)
```

---

### 6. List Endpoints Return Paginated Envelope

List endpoints no longer return a bare array. They now return a paginated envelope with `items`, `total`, and `next_cursor`. Use cursor-based pagination instead of offset.

**Before (v1):**
```json
// GET /tasks
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

```javascript
// JavaScript — direct array access
const tasks = await response.json();
tasks.forEach(task => console.log(task.title));
```

```python
# Python — list directly
tasks = response.json()
for task in tasks:
    print(task["title"])
```

**After (v2):**
```json
// GET /v2/tasks
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false},
    {"id": "c3d4...", "title": "Ship v2", "completed": true}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// JavaScript — extract items from envelope
const data = await response.json();
const tasks = data.items;
data.items.forEach(task => console.log(task.title));

// Pagination
const nextPage = await fetch(`/v2/tasks?cursor=${data.next_cursor}`);
```

```python
# Python — extract items from envelope
data = response.json()
tasks = data["items"]
for task in tasks:
    print(task["title"])

# Pagination
next_page = requests.get(f'/v2/tasks?cursor={data["next_cursor"]}')
```

---

## Migration Checklist

Use this checklist to ensure your migration is complete:

- [ ] Update base URLs to include `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] Update type definitions: change task `id` from `number`/`int` to `string` (UUID)
- [ ] Rename all references from `done` to `completed` in request bodies and responses
- [ ] Add `project_id` to all task creation requests
- [ ] Update list endpoint handling to parse paginated envelope (`items`, `total`, `next_cursor`)
- [ ] Implement cursor-based pagination (replace offset/limit if used)
- [ ] Update test mocks and fixtures to reflect new data types
- [ ] Verify error handling for new HTTP 422 responses (missing `project_id`)
- [ ] Run integration tests against v2 endpoints

---

## Upgrade Command

Install the latest v2 CLI:

```bash
npm install -g @zrb/cli@latest
# or
pip install --upgrade zrb-cli
```

Verify your installation:

```bash
zrb --version  # Should output 2.x.x
```

---

## Need Help?

- Review the full [v2 API specification](v2_spec.md)
- [Open an issue](https://github.com/zrb-io/zrb/issues) for migration questions
- Join the [Discord community](https://discord.gg/zrb) for real-time support
