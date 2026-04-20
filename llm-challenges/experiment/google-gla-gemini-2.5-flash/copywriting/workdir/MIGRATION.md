# Zrb CLI v1 to v2 Migration Guide

This guide details the breaking changes and necessary steps to migrate your existing Zrb CLI v1 integrations to v2. Zrb CLI v2 introduces significant improvements including project management, enhanced authentication, and better pagination.

## Breaking Changes

### 1. Endpoint Prefix Change

All API endpoints in v2 are now prefixed with `/v2/`. This ensures versioning and allows for future API evolution.

**Before (v1)**
```
GET /tasks
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2)**
```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

**Example: Listing tasks**

**v1**
```python
import requests

api_key = "YOUR_V1_API_KEY"
headers = {"X-Auth-Token": api_key}
response = requests.get("https://api.zrb.com/tasks", headers=headers)
tasks = response.json()
print(tasks)
```

**v2**
```python
import requests

api_token = "YOUR_V2_API_TOKEN"
headers = {"Authorization": f"Bearer {api_token}"}
response = requests.get("https://api.zrb.com/v2/tasks", headers=headers)
paginated_response = response.json()
tasks = paginated_response["items"]
print(tasks)
```

### 2. Authentication Header Changed

The authentication mechanism has been updated for improved security. The `X-Auth-Token` header is no longer supported. You must now use a Bearer token in the `Authorization` header. Requests using the old header will receive an HTTP 401 Unauthorized response.

**Before (v1)**
```
X-Auth-Token: <your_api_key>
```

**After (v2)**
```
Authorization: Bearer <your_api_token>
```

**Example: Authenticating a request**

**v1**
```python
import requests

api_key = "YOUR_V1_API_KEY"
headers = {"X-Auth-Token": api_key}
# ... make API calls with these headers
```

**v2**
```python
import requests

api_token = "YOUR_V2_API_TOKEN"
headers = {"Authorization": f"Bearer {api_token}"}
# ... make API calls with these headers
```

### 3. Task `id` Type Changed from Integer to UUID String

The `id` field for Task objects is no longer an auto-assigned integer. It is now a UUID string, providing a more robust and globally unique identifier.

**Before (v1) Task Object**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2) Task Object**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Example: Getting a specific task**

**v1**
```python
task_id = 42 # Integer ID
response = requests.get(f"https://api.zrb.com/tasks/{task_id}", headers=headers)
task = response.json()
print(task["id"]) # Output: 42
```

**v2**
```python
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890" # UUID string ID
response = requests.get(f"https://api.zrb.com/v2/tasks/{task_id}", headers=headers)
task = response.json()
print(task["id"]) # Output: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 4. Task Field `done` Renamed to `completed`

The boolean field indicating the completion status of a task has been renamed from `done` to `completed`.

**Before (v1)**
```json
{ "title": "Buy milk", "done": true }
```

**After (v2)**
```json
{ "title": "Buy milk", "completed": true }
```

**Example: Updating a task's status**

**v1**
```python
task_id = 42
update_payload = {"done": True}
response = requests.put(f"https://api.zrb.com/tasks/{task_id}", headers=headers, json=update_payload)
updated_task = response.json()
print(updated_task["done"]) # Output: True
```

**v2**
```python
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
update_payload = {"completed": True}
response = requests.put(f"https://api.zrb.com/v2/tasks/{task_id}", headers=headers, json=update_payload)
updated_task = response.json()
print(updated_task["completed"]) # Output: True
```

### 5. Task Creation Now Requires `project_id`

In v2, all tasks must belong to a project. Therefore, the `project_id` field is now mandatory when creating a new task. Omitting it will result in an HTTP 422 Unprocessable Entity error.

**Before (v1) Request Body for Create Task**
```json
{
  "title": "New task title"
}
```

**After (v2) Request Body for Create Task**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Example: Creating a task**

**v1**
```python
create_payload = {"title": "Draft migration guide"}
response = requests.post("https://api.zrb.com/tasks", headers=headers, json=create_payload)
new_task = response.json()
print(new_task)
```

**v2**
```python
create_payload = {"title": "Draft migration guide", "project_id": "your_project_uuid"}
response = requests.post("https://api.zrb.com/v2/tasks", headers=headers, json=create_payload)
new_task = response.json()
print(new_task)
```

### 6. List Endpoints Return a Paginated Envelope

All list endpoints (e.g., `/v2/tasks`) no longer return a bare array of objects. Instead, they return a paginated envelope containing the items, total count, and a `next_cursor` for fetching subsequent pages.

**Before (v1) List Tasks Response**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) List Tasks Response (Paginated Envelope)**
```json
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch subsequent pages, include the `cursor` query parameter: `GET /v2/tasks?cursor=cursor_xyz`. You can also specify `limit` (default 20) for results per page.

**Example: Iterating through tasks**

**v1**
```python
response = requests.get("https://api.zrb.com/tasks", headers=headers)
tasks = response.json()
for task in tasks:
    print(task["title"])
```

**v2**
```python
tasks = []
next_cursor = None

while True:
    params = {}
    if next_cursor:
        params["cursor"] = next_cursor

    response = requests.get("https://api.zrb.com/v2/tasks", headers=headers, params=params)
    paginated_response = response.json()

    tasks.extend(paginated_response["items"])
    next_cursor = paginated_response.get("next_cursor")

    if not next_cursor:
        break

for task in tasks:
    print(task["title"])
```

## Migration Checklist

1.  [ ] **Update CLI version**: Ensure your Zrb CLI is updated to v2.
2.  [ ] **Generate New API Token**: Obtain a new API token compatible with v2 authentication.
3.  [ ] **Update Authentication Header**: Change `X-Auth-Token` to `Authorization: Bearer <your_api_token>` in all API requests.
4.  [ ] **Modify Endpoint Paths**: Prefix all `/tasks` endpoints with `/v2/`.
5.  [ ] **Adjust Task ID Handling**: Update any code that expects integer task IDs to handle UUID strings instead.
6.  [ ] **Rename `done` field**: Replace all occurrences of `done` with `completed` in Task objects (creation, update, and retrieval).
7.  [ ] **Add `project_id` to Task Creation**: Ensure all `POST /v2/tasks` requests include a valid `project_id` in the request body.
8.  [ ] **Refactor List Endpoint Responses**: Update code that consumes list endpoints (e.g., `GET /v2/tasks`) to parse the new paginated envelope structure and handle pagination cursors.
9.  [ ] **Test Thoroughly**: Run all your existing integration and unit tests to ensure compatibility and correct functionality with the new v2 API.

## Upgrade Command

To upgrade your Zrb CLI to the latest v2 version, run:

```bash
zrb upgrade --v2
```
