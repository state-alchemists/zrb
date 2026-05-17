# Migrating from Zrb Task API v1 to v2

v2 introduces projects, cursor-based pagination, and stronger authentication. This guide covers every breaking change and what you need to update in your integration.

---

## Breaking Changes

### 1. Endpoint paths now require `/v2/` prefix

All task endpoints are now under the `/v2/` path prefix. Calls to the old paths will return `404`.

| v1                    | v2                        |
|-----------------------|---------------------------|
| `GET /tasks`          | `GET /v2/tasks`           |
| `GET /tasks/{id}`     | `GET /v2/tasks/{id}`      |
| `POST /tasks`         | `POST /v2/tasks`          |
| `PUT /tasks/{id}`     | `PUT /v2/tasks/{id}`      |
| `DELETE /tasks/{id}`  | `DELETE /v2/tasks/{id}`   |

**Before:**
```bash
curl https://api.zrb.dev/tasks -H "X-Auth-Token: $API_KEY"
```

**After:**
```bash
curl https://api.zrb.dev/v2/tasks -H "Authorization: Bearer $API_KEY"
```

### 2. Authentication header changed

The `X-Auth-Token` header is no longer accepted. Use the standard `Authorization: Bearer` header instead. Requests that include `X-Auth-Token` will receive `HTTP 401 Unauthorized`.

**Before:**
```python
headers = {"X-Auth-Token": api_key}
```

**After:**
```python
headers = {"Authorization": f"Bearer {api_key}"}
```

### 3. Task `id` changed from integer to UUID string

The `id` field on task objects is now a UUID string instead of an auto-incrementing integer. Any code that parses, stores, or validates task IDs as integers will break.

**Before:**
```json
{"id": 42, "title": "Write tests", "done": false, "created_at": "..."}
```

**After:**
```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false, "project_id": "proj_abc123", "created_at": "..."}
```

**Before:**
```python
task_id: int = response["id"]
```

**After:**
```python
task_id: str = response["id"]
```

If you use task IDs in URL paths, query parameters, or database columns, update those to store and handle strings instead of integers.

### 4. Task field `done` renamed to `completed`

The boolean field `done` has been renamed to `completed`. This affects both task responses and update request bodies.

**Before:**
```python
# Reading task state
if task["done"]:
    print("Task finished!")

# Updating a task
requests.put("/tasks/42", json={"done": True})
```

**After:**
```python
# Reading task state
if task["completed"]:
    print("Task finished!")

# Updating a task
requests.put(f"/v2/tasks/{task_id}", json={"completed": True})
```

### 5. `project_id` is now required when creating tasks

Creating a task without a `project_id` returns `HTTP 422 Unprocessable Entity`. You must specify which project the task belongs to.

**Before:**
```json
{
  "title": "New task title"
}
```

**After:**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. List endpoints return a paginated envelope instead of a bare array

`GET /v2/tasks` no longer returns a bare JSON array. The response is now a paginated envelope containing `items`, `total`, and `next_cursor`.

**Before:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After:**
```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "e5f6...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Any code that iterates the response directly as an array will need to unwrap `items` first. To fetch the next page, pass `?cursor=<next_cursor>`. You can also set `?limit=<n>` (default: 20).

**Before:**
```python
tasks = requests.get("/tasks", headers=headers).json()
for task in tasks:
    print(task["title"])
```

**After:**
```python
cursor = None
while True:
    params = {"limit": 20}
    if cursor:
        params["cursor"] = cursor
    data = requests.get("/v2/tasks", headers=headers, params=params).json()
    for task in data["items"]:
        print(task["title"])
    cursor = data.get("next_cursor")
    if not cursor:
        break
```

---

## Migration Checklist

- [ ] Update all API paths to include the `/v2/` prefix
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer` header
- [ ] Update task ID handling: change from `int` to `str` (UUID) in types, databases, and URL routing
- [ ] Rename all references to the `done` field to `completed` (read paths and write paths)
- [ ] Add `project_id` to all task creation requests
- [ ] Update list-endpoint consumers: unwrap `items` from the paginated envelope instead of treating the response as a bare array
- [ ] Implement cursor-based pagination for list endpoints if you need more than the default 20 results per page
- [ ] Remove any integer-based ID validation or sequencing assumptions
- [ ] Run your test suite against the v2 API and fix failing assertions

---

## Upgrade

```bash
pip install --upgrade zrb
```