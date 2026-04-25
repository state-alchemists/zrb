# Zrb CLI Migration Guide: v1 → v2

This guide helps you migrate your existing Zrb CLI integrations from v1 to v2. v2 introduces projects, improved pagination, and stricter authentication.

---

## Breaking Changes Overview

| Change | v1 | v2 |
|--------|-----|-----|
| Base URL | `/tasks` | `/v2/tasks` |
| Authentication | `X-Auth-Token` header | `Authorization: Bearer` header |
| Task ID type | Integer (`42`) | UUID string (`"a1b2c3d4-..."`) |
| Completion field | `done` | `completed` |
| Task creation | `title` only | `title` + required `project_id` |
| List response | Bare array | Paginated envelope |

---

## 1. Endpoint Prefix

**Breaking Change:** All endpoints are now prefixed with `/v2/`.

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

---

## 2. Authentication Header

**Breaking Change:** The authentication header has changed from `X-Auth-Token` to Bearer token format.

### Before (v1)
```bash
curl -H "X-Auth-Token: <your_api_key>" \
  https://api.zrb.io/tasks
```

```javascript
// JavaScript
headers: {
  "X-Auth-Token": apiKey
}
```

```python
# Python
headers = {"X-Auth-Token": api_key}
```

### After (v2)
```bash
curl -H "Authorization: Bearer <your_api_token>" \
  https://api.zrb.io/v2/tasks
```

```javascript
// JavaScript
headers: {
  "Authorization": `Bearer ${apiToken}`
}
```

```python
# Python
headers = {"Authorization": f"Bearer {api_token}"}
```

> ⚠️ **Note:** Requests using the old `X-Auth-Token` header will receive HTTP 401 Unauthorized.

---

## 3. Task ID Type

**Breaking Change:** Task IDs have changed from integers to UUID strings.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
// JavaScript - storing as number
const taskId = response.data.id; // 42
```

```python
# Python - storing as int
task_id = response.json()["id"]  # 42
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

```javascript
// JavaScript - now a string
const taskId = response.data.id; // "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

```python
# Python - now a string
task_id = response.json()["id"]  # "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

> ⚠️ **Note:** Update your data models to treat `id` as a string type, not integer.

---

## 4. Task Field Renamed: `done` → `completed`

**Breaking Change:** The boolean field indicating task completion has been renamed from `done` to `completed`.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
// JavaScript
if (task.done) { /* ... */ }
const payload = { done: true };
```

```python
# Python
if task["done"]:
    pass
payload = {"done": True}
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

```javascript
// JavaScript
if (task.completed) { /* ... */ }
const payload = { completed: true };
```

```python
# Python
if task["completed"]:
    pass
payload = {"completed": True}
```

---

## 5. Task Creation Requires `project_id`

**Breaking Change:** Creating a task now requires a `project_id` field. Requests without it return HTTP 422.

### Before (v1)
```bash
curl -X POST https://api.zrb.io/tasks \
  -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

```javascript
// JavaScript
const response = await axios.post('/tasks', {
  title: 'New task'
});
```

```python
# Python
response = requests.post("/tasks", json={"title": "New task"})
```

### After (v2)
```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New task",
    "project_id": "proj_abc123"
  }'
```

```javascript
// JavaScript
const response = await axios.post('/v2/tasks', {
  title: 'New task',
  project_id: 'proj_abc123'
});
```

```python
# Python
response = requests.post(
    "/v2/tasks",
    json={
        "title": "New task",
        "project_id": "proj_abc123"
    }
)
```

> ⚠️ **Note:** If you haven't set up projects yet, you'll need to create one first to obtain a `project_id`.

---

## 6. List Endpoints Return Paginated Envelope

**Breaking Change:** `GET /tasks` no longer returns a bare array. It now returns a paginated envelope with `items`, `total`, and `next_cursor`.

### Before (v1)
```bash
curl -H "X-Auth-Token: <your_api_key>" \
  https://api.zrb.io/tasks
```

**Response:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
// JavaScript - direct array access
const tasks = response.data; // Array
const titles = tasks.map(t => t.title);
```

```python
# Python - direct list access
tasks = response.json()  # List
for task in tasks:
    print(task["title"])
```

### After (v2)
```bash
curl -H "Authorization: Bearer <your_api_token>" \
  https://api.zrb.io/v2/tasks?limit=20
```

**Response:**
```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v2", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// JavaScript - extract items from envelope
const tasks = response.data.items; // Array inside envelope
const total = response.data.total;
const nextCursor = response.data.next_cursor; // null if no more pages

// Fetch next page
if (nextCursor) {
  const nextPage = await axios.get(`/v2/tasks?cursor=${nextCursor}`);
}
```

```python
# Python - extract items from envelope
data = response.json()
tasks = data["items"]  # List inside envelope
total = data["total"]
next_cursor = data["next_cursor"]  # None if no more pages

# Fetch next page
if next_cursor:
    next_page = requests.get(f"/v2/tasks?cursor={next_cursor}")
```

> ℹ️ **Tip:** Use `?limit=<n>` to control page size (default is 20).

---

## Migration Checklist

Use this checklist to ensure a complete migration:

- [ ] **Update imports/base URL configuration** to use `/v2/` prefix for all endpoints
- [ ] **Update authentication headers** from `X-Auth-Token` to `Authorization: Bearer <token>`
- [ ] **Review API token storage** — ensure you're using the new v2 API tokens
- [ ] **Update Task data models** to change `id` from `int`/`number` to `string`/`UUID`
- [ ] **Rename `done` field to `completed`** in all request payloads and response handling
- [ ] **Add `project_id` to task creation** — identify or create a project first
- [ ] **Update list task handling** — extract items from paginated envelope (`data.items` instead of `data`)
- [ ] **Implement pagination support** — handle `next_cursor` for fetching additional pages
- [ ] **Update unit tests** to use new field names and data types
- [ ] **Update integration tests** to verify v2 endpoints
- [ ] **Review error handling** — 401 errors may indicate old auth header; 422 errors may indicate missing `project_id`
- [ ] **Update documentation** for your own API consumers
- [ ] **Deploy to staging** and run full test suite
- [ ] **Monitor error rates** after production deployment

---

## Upgrade Command

To upgrade your CLI to v2:

```bash
zrb self-update --version=2
```

Or install fresh:

```bash
npm install -g @zrb/cli@2
# or
pip install zrb-cli==2.0.0
```

---

## Need Help?

- [v2 API Reference](v2_spec.md)
- [Report migration issues](https://github.com/zrb-io/cli/issues)
- [Community Discord](https://discord.gg/zrb)
