# Migrating from Zrb API v1 to v2

v2 introduces projects, cursor-based pagination, and modernized authentication. This guide covers each breaking change with migration examples.

## Breaking Changes Overview

| Change | Impact |
|-------|--------|
| [Authentication header](#1-authentication-header) | All requests |
| [Endpoint prefix](#2-endpoint-prefix) | All endpoints |
| [Task ID type](#3-task-id-type) | URL params, references |
| [Field rename: `done` → `completed`](#4-field-rename-done--completed) | Request/response bodies |
| [Required `project_id`](#5-required-project_id) | Task creation |
| [Paginated list response](#6-paginated-list-response) | List endpoints |

---

## 1. Authentication Header

The auth header changed from a custom header to standard Bearer token.

**Before (v1):**
```http
GET /tasks HTTP/1.1
X-Auth-Token: your_api_key
```

**After (v2):**
```http
GET /v2/tasks HTTP/1.1
Authorization: Bearer your_api_token
```

Requests using the old `X-Auth-Token` header will receive **HTTP 401 Unauthorized**.

---

## 2. Endpoint Prefix

All endpoints now require the `/v2/` prefix.

**Before (v1):**
```
GET /tasks
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**
```
GET /v2/tasks
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

## 3. Task ID Type

Task IDs changed from integers to UUID strings.

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

**Migration impact:**
- URL references: `/tasks/42` → `/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890`
- Client code: Change ID type from `int` to `string`
- Database: If storing IDs, update column type to `VARCHAR(36)` or `UUID`

---

## 4. Field Rename: `done` → `completed`

The task status field was renamed for clarity.

**Before (v1):**
```json
{
  "id": 1,
  "title": "Buy milk",
  "done": false
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Buy milk",
  "completed": false
}
```

**Update request (v1):**
```json
{
  "done": true
}
```

**Update request (v2):**
```json
{
  "completed": true
}
```

---

## 5. Required `project_id`

Task creation now requires a `project_id`. This enables project-based organization.

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

Omitting `project_id` returns **HTTP 422 Unprocessable Entity**.

---

## 6. Paginated List Response

List endpoints now return a paginated envelope instead of a bare array.

**Before (v1):**
```json
GET /tasks

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```json
GET /v2/tasks

{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "uuid-2", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Pagination:**
- Default limit: 20 items per page
- Fetch next page: `GET /v2/tasks?cursor=cursor_xyz`
- Customize limit: `GET /v2/tasks?limit=50`

**Code migration:**
```python
# Before (v1)
response = requests.get("/tasks", headers={"X-Auth-Token": api_key})
tasks = response.json()  # Direct array

# After (v2)
response = requests.get(
    "/v2/tasks",
    headers={"Authorization": f"Bearer {api_token}"}
)
data = response.json()
tasks = data["items"]  # Extract from envelope
total = data["total"]
next_cursor = data.get("next_cursor")
```

---

## Full Example: Create and List Tasks

**Before (v1):**
```python
import requests

API_KEY = "your_api_key"
BASE_URL = "https://api.zrb.dev"

headers = {"X-Auth-Token": API_KEY}

# Create task
response = requests.post(
    f"{BASE_URL}/tasks",
    headers=headers,
    json={"title": "Write tests"}
)
task = response.json()
task_id = task["id"]  # integer

# List tasks
response = requests.get(f"{BASE_URL}/tasks", headers=headers)
tasks = response.json()  # bare array

# Mark done
requests.put(
    f"{BASE_URL}/tasks/{task_id}",
    headers=headers,
    json={"done": True}
)
```

**After (v2):**
```python
import requests

API_TOKEN = "your_api_token"
BASE_URL = "https://api.zrb.dev"
PROJECT_ID = "proj_abc123"

headers = {"Authorization": f"Bearer {API_TOKEN}"}

# Create task
response = requests.post(
    f"{BASE_URL}/v2/tasks",
    headers=headers,
    json={"title": "Write tests", "project_id": PROJECT_ID}
)
task = response.json()
task_id = task["id"]  # UUID string

# List tasks
response = requests.get(f"{BASE_URL}/v2/tasks", headers=headers)
data = response.json()
tasks = data["items"]  # extract from envelope

# Mark completed
requests.put(
    f"{BASE_URL}/v2/tasks/{task_id}",
    headers=headers,
    json={"completed": True}
)
```

---

## Migration Checklist

- [ ] **Update authentication**: Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] **Update base URL**: Add `/v2/` prefix to all endpoints (or update base URL to include it)
- [ ] **Change ID handling**: Update task ID type from `int` to `string` (UUID format)
- [ ] **Rename field**: Replace all references to `done` with `completed`
- [ ] **Add project support**: Ensure `project_id` is provided when creating tasks
- [ ] **Handle pagination**: Update list endpoints to extract `items` from the response envelope
- [ ] **Update types/schemas**: If using typed clients, update ID types, field names, and response shapes
- [ ] **Test all endpoints**: Verify each integration point works with v2 changes

---

## Upgrade Command

```bash
pip install zrb==2.0.0
```