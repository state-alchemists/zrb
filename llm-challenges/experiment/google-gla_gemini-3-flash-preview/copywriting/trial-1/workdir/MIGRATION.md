# Zrb Task API — v1 to v2 Migration Guide

v2 introduces projects, cursor-based pagination, stricter authentication, and several cleanups to the task object schema. Every breaking change is covered below with before/after examples so you can migrate incrementally and with confidence.

**Audience:** Developers actively using the v1 API.

---

## Breaking Changes

### 1. Authentication Header

`X-Auth-Token` has been replaced with the standard `Authorization: Bearer` header. Requests using the old header will receive HTTP 401.

**Before (v1):**

```http
X-Auth-Token: your_api_key
```

**After (v2):**

```http
Authorization: Bearer your_api_token
```

---

### 2. Endpoint Prefix

All endpoints are now prefixed with `/v2/`. The old paths will return HTTP 404.

| Operation | v1 | v2 |
|-----------|----|----|
| List tasks | `GET /tasks` | `GET /v2/tasks` |
| Get task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create task | `POST /tasks` | `POST /v2/tasks` |
| Update task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks \
  -H "X-Auth-Token: $TOKEN"
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer $TOKEN"
```

---

### 3. Task ID Type: Integer → UUID String

Task `id` values are now UUID strings instead of auto-incrementing integers. Existing integer IDs have been migrated to their UUID equivalents. You must update any code that casts, stores, or compares task IDs as integers.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

**Impact on client code:**

```python
# Before (v1)
task_id = response["id"]  # int — e.g., 42
url = f"/tasks/{task_id}"

# After (v2)
task_id = response["id"]  # str — e.g., "a1b2c3d4-..."
url = f"/v2/tasks/{task_id}"
```

```typescript
// Before (v1)
const taskId: number = task.id;

// After (v2)
const taskId: string = task.id;
```

---

### 4. `done` Renamed to `completed`

The boolean task status field has been renamed from `done` to `completed`. The old field name will be silently ignored in requests and omitted in responses.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

**Read-side migration:**

```python
# Before (v1)
is_done = task["done"]

# After (v2)
is_done = task["completed"]
```

**Write-side migration — update request:**

```bash
# Before (v1)
curl -X PUT https://api.zrb.dev/tasks/42 \
  -H "X-Auth-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"done": true}'

# After (v2)
curl -X PUT https://api.zrb.dev/v2/tasks/a1b2c3d4-... \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

---

### 5. `project_id` Required on Create

Every task must now belong to a project. `project_id` is a required field when creating a task. Omitting it returns HTTP 422.

**Before (v1):** Only `title` was needed.

```json
{
  "title": "New task title"
}
```

**After (v2):** `project_id` is required.

```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

To obtain a project ID, list your projects:

```bash
curl https://api.zrb.dev/v2/projects \
  -H "Authorization: Bearer $TOKEN"
```

---

### 6. List Response: Bare Array → Paginated Envelope

List endpoints no longer return a bare array. They return a paginated envelope object containing `items`, `total`, and `next_cursor`.

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
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "d4e5...", "title": "Ship v2", "completed": true, "created_at": "..."}
  ],
  "total": 256,
  "next_cursor": "cursor_xyz"
}
```

**Client code migration:**

```python
# Before (v1)
tasks = response  # bare list

# After (v2)
tasks = response["items"]         # list of tasks
total = response["total"]          # total count across all pages
next_cursor = response.get("next_cursor")  # None if last page
```

---

### 7. Cursor-Based Pagination (New)

Lists are now paginated by default (20 items per page). Use `?cursor=` and `?limit=` to navigate pages.

**Before (v1):** No pagination — all results returned in a single response.

**After (v2):**

```bash
# First page (default: limit=20)
curl "https://api.zrb.dev/v2/tasks?limit=20" \
  -H "Authorization: Bearer $TOKEN"

# Subsequent pages
curl "https://api.zrb.dev/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

```python
# After (v2) — full pagination loop
def get_all_tasks():
    tasks = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(
            "https://api.zrb.dev/v2/tasks",
            params=params,
            headers={"Authorization": f"Bearer {TOKEN}"}
        )
        data = resp.json()
        tasks.extend(data["items"])
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return tasks
```

---

## Migration Checklist

Use this checklist to track your migration progress task by task.

- [ ] **Update authentication**: Replace `X-Auth-Token` header with `Authorization: Bearer`.
- [ ] **Prefix endpoints**: Prepend `/v2` to all API paths.
- [ ] **Handle UUID IDs**: Update ID storage, comparison, and URL construction to use strings instead of integers.
- [ ] **Rename `done` → `completed`**: Update all read and write paths that reference the task status field.
- [ ] **Add `project_id`**: Supply a project ID on every task creation call. Update any task creation UI or scripts.
- [ ] **Unwrap list responses**: Access `response["items"]` instead of consuming the response as a bare array.
- [ ] **Adopt cursor pagination**: Replace any offset/limit logic with cursor-based pagination using `next_cursor`.

---

## Upgrade Command

Install the latest Zrb CLI to start using v2:

```bash
pip install --upgrade zrb
```

Verify the installed version:

```bash
zrb --version
# Expected: 2.x.x
```
