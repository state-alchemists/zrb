# Zrb CLI v1 to v2 Migration Guide

This guide details the breaking changes introduced in Zrb CLI v2 and provides step-by-step instructions for migrating your existing v1 integrations. v2 brings significant improvements, including project support and better pagination, but requires updates to your code.

## Breaking Changes

### 1. Endpoint Prefix Change

All API endpoints are now prefixed with `/v2/`. This ensures versioning and allows for future API evolution.

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

**Migration Example:**

**v1:**
```python
import requests

api_key = "YOUR_V1_API_KEY"
response = requests.get("https://api.zrb.com/tasks", headers={"X-Auth-Token": api_key})
print(response.json())
```

**v2:**
```python
import requests

api_token = "YOUR_V2_API_TOKEN" # Note: New token format
response = requests.get("https://api.zrb.com/v2/tasks", headers={"Authorization": f"Bearer {api_token}"})
print(response.json())
```

### 2. Authentication Header Changed

The authentication mechanism has been updated from a custom header (`X-Auth-Token`) to a standard Bearer token in the `Authorization` header. Requests using the old header will receive an HTTP 401 Unauthorized response.

**Before (v1):**
```
X-Auth-Token: <your_api_key>
```

**After (v2):**
```
Authorization: Bearer <your_api_token>
```

**Migration Example:**

**v1:**
```python
headers = {
    "X-Auth-Token": "your_v1_api_key"
}
```

**v2:**
```python
headers = {
    "Authorization": "Bearer your_v2_api_token"
}
```

### 3. Task `id` Type Change

The `id` field for Task objects has changed from an integer to a UUID string. This provides a more robust and universally unique identifier.

**Before (v1 - Task Object):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2 - Task Object):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Migration Example (fetching a task):**

**v1:**
```python
task_id_v1 = 42
response = requests.get(f"https://api.zrb.com/tasks/{task_id_v1}", headers=v1_headers)
```

**v2:**
```python
task_id_v2 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
response = requests.get(f"https://api.zrb.com/v2/tasks/{task_id_v2}", headers=v2_headers)
```

### 4. Task Field `done` Renamed to `completed`

The boolean field indicating task completion has been renamed from `done` to `completed` for improved clarity and consistency.

**Before (v1 - Task Object):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2 - Task Object):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Migration Example (updating a task):**

**v1:**
```python
update_payload_v1 = {
    "done": True
}
response = requests.put(f"https://api.zrb.com/tasks/{task_id_v1}", json=update_payload_v1, headers=v1_headers)
```

**v2:**
```python
update_payload_v2 = {
    "completed": True
}
response = requests.put(f"https://api.zrb.com/v2/tasks/{task_id_v2}", json=update_payload_v2, headers=v2_headers)
```

### 5. Task Creation Now Requires `project_id`

When creating a new task, the `project_id` field is now mandatory. This allows for better organization and management of tasks within projects. Omitting `project_id` will result in an HTTP 422 Unprocessable Entity response.

**Before (v1 - Create Task Request Body):**
```json
{
  "title": "New task title"
}
```

**After (v2 - Create Task Request Body):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Migration Example (creating a task):**

**v1:**
```python
create_payload_v1 = {
    "title": "Plan v2 release"
}
response = requests.post("https://api.zrb.com/tasks", json=create_payload_v1, headers=v1_headers)
```

**v2:**
```python
create_payload_v2 = {
    "title": "Plan v2 release",
    "project_id": "proj_alpha"
}
response = requests.post("https://api.zrb.com/v2/tasks", json=create_payload_v2, headers=v2_headers)
```

### 6. List Endpoints Return a Paginated Envelope

All list endpoints (e.g., `GET /v2/tasks`) no longer return a bare array of task objects. Instead, they return a paginated envelope containing the `items`, `total` count, and `next_cursor` for fetching subsequent pages.

**Before (v1 - List Tasks Response):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2 - List Tasks Response):**
```json
{
  "items": [
    {"id": "uuid1", "title": "Buy milk", "completed": false, "project_id": "proj_retail", "created_at": "..."},
    {"id": "uuid2", "title": "Ship v1", "completed": true, "project_id": "proj_internal", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

**Migration Example (listing tasks):**

**v1:**
```python
response = requests.get("https://api.zrb.com/tasks", headers=v1_headers)
tasks = response.json()
for task in tasks:
    print(task["title"])
```

**v2:**
```python
response = requests.get("https://api.zrb.com/v2/tasks", headers=v2_headers)
paginated_response = response.json()
tasks = paginated_response["items"]
for task in tasks:
    print(task["title"])

# To get the next page:
# next_cursor = paginated_response.get("next_cursor")
# if next_cursor:
#     response = requests.get(f"https://api.zrb.com/v2/tasks?cursor={next_cursor}", headers=v2_headers)
#     next_page_data = response.json()
```

## Migration Checklist

1.  [ ] **Update API Endpoint URLs:** Change all `/tasks` endpoint calls to `/v2/tasks`.
2.  [ ] **Switch Authentication:** Replace `X-Auth-Token` headers with `Authorization: Bearer <your_api_token>`. Obtain a new v2 API token if necessary.
3.  [ ] **Handle Task `id` Type:** Update any code that stores or processes task IDs to expect UUID strings instead of integers.
4.  [ ] **Rename `done` to `completed`:** Update all references to the `done` field in Task objects to `completed`.
5.  [ ] **Add `project_id` to Task Creation:** Ensure all `POST /v2/tasks` requests include a `project_id` in the request body.
6.  [ ] **Process Paginated Responses:** Modify code that consumes list endpoints to parse the `items` array from the paginated envelope and handle `next_cursor` for subsequent pages.
7.  [ ] **Test Thoroughly:** After making these changes, run your test suite to ensure all integrations are working correctly with the v2 API.

## Upgrade Command

To upgrade your Zrb CLI to v2, run:

```bash
zrb upgrade --version v2
```