# Zrb Task API — Migrating from v1 to v2

This guide covers every breaking change between v1 and v2 of the Zrb Task API. If you're currently integrating against v1, follow the sections below to update your code.

---

## Breaking Changes

### 1. Endpoint prefix: all routes now live under `/v2/`

Every endpoint path is now prefixed with `/v2/`. Requests to the old unprefixed paths will return 404.

**Before (v1)**

```bash
curl https://api.zrb.dev/tasks
curl https://api.zrb.dev/tasks/42
curl -X POST https://api.zrb.dev/tasks
curl -X PUT https://api.zrb.dev/tasks/42
curl -X DELETE https://api.zrb.dev/tasks/42
```

**After (v2)**

```bash
curl https://api.zrb.dev/v2/tasks
curl https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl -X POST https://api.zrb.dev/v2/tasks
curl -X PUT https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl -X DELETE https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

If you use a base URL constant, this may be a one-line fix:

**Before (v1)**

```python
BASE_URL = "https://api.zrb.dev"
```

**After (v2)**

```python
BASE_URL = "https://api.zrb.dev/v2"
```

---

### 2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer`

The `X-Auth-Token` header is no longer accepted. Requests that send it will receive **HTTP 401**.

**Before (v1)**

```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.dev/tasks
```

**After (v2)**

```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.dev/v2/tasks
```

**Before (v1)**

```python
headers = {"X-Auth-Token": API_KEY}
```

**After (v2)**

```python
headers = {"Authorization": f"Bearer {API_TOKEN}"}
```

> **Note:** your existing API key value does not change — only the header name and format change.

---

### 3. Task `id` changed from integer to UUID string

Task IDs are now UUID strings instead of auto-incrementing integers. Any code that assumes `id` is an integer (type checks, DB schemas, URL routing patterns) must be updated.

**Before (v1)**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2)**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Common code that needs updating:**

- Database columns: change from `INTEGER` to `VARCHAR(36)` (or your DB's UUID type).
- Type annotations: change from `int` to `str`.
- URL validation: update regex patterns from `\d+` to UUID format (e.g. `[0-9a-f-]{36}`).

**Before (v1)**

```python
def get_task(task_id: int):
    return httpx.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
```

**After (v2)**

```python
def get_task(task_id: str):
    return httpx.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
```

---

### 4. Task field `done` renamed to `completed`

The boolean field `done` has been renamed to `completed`. Sending `"done": true` in a request body will be ignored (not an error, but the field won't update the task).

**Before (v1)** — reading

```python
if task["done"]:
    print("Task is finished")
```

**After (v2)** — reading

```python
if task["completed"]:
    print("Task is finished")
```

**Before (v1)** — updating

```json
{
  "done": true
}
```

**After (v2)** — updating

```json
{
  "completed": true
}
```

---

### 5. Task creation now requires `project_id`

The `POST /v2/tasks` endpoint requires a `project_id` field in the request body. Omitting it returns **HTTP 422**.

**Before (v1)**

```json
{
  "title": "New task title"
}
```

**After (v2)**

```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Before (v1)**

```python
task = client.post(f"{BASE_URL}/tasks", json={"title": "Write docs"})
```

**After (v2)**

```python
task = client.post(
    f"{BASE_URL}/tasks",
    json={"title": "Write docs", "project_id": "proj_abc123"},
)
```

If you don't yet have a project setup, you'll need to create one first or obtain a `project_id` from your organization admin.

---

### 6. List endpoints return a paginated envelope instead of a bare array

`GET /v2/tasks` no longer returns a bare JSON array. It now returns a paginated envelope, and response parsing code that iterates the top-level array will break.

**Before (v1)**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2)**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "c3d4...", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Pagination uses cursor-based navigation via the `?cursor` query parameter. Pass `?limit=N` to control page size (default 20).

**Before (v1)** — fetch all tasks

```python
tasks = httpx.get(f"{BASE_URL}/tasks", headers=headers).json()
for task in tasks:
    print(task["title"])
```

**After (v2)** — fetch all tasks with pagination

```python
cursor = None
while True:
    params = {}
    if cursor:
        params["cursor"] = cursor
    page = httpx.get(f"{BASE_URL}/tasks", headers=headers, params=params).json()
    for task in page["items"]:
        print(task["title"])
    cursor = page.get("next_cursor")
    if not cursor:
        break
```

---

## Migration Checklist

Work through these steps in order. Each step is independently testable.

- [ ] **1. Update base URL** — Add `/v2` prefix to your API base URL constant or every endpoint path.
- [ ] **2. Update auth header** — Replace `X-Auth-Token` with `Authorization: Bearer`. Remove any `X-Auth-Token` usage.
- [ ] **3. Update task ID handling** — Change `id` type from `int` to `str` in models, DB schemas, type annotations, and URL validators.
- [ ] **4. Rename `done` to `completed`** — Update all read and write references: response parsing, request bodies, conditionals, and display logic.
- [ ] **5. Add `project_id` to task creation** — Ensure every `POST /v2/tasks` request includes a `project_id`. Add logic to obtain or configure a valid project ID.
- [ ] **6. Update list response parsing** — Stop iterating the raw response as an array. Extract `items` from the paginated envelope. Implement cursor-based pagination if you need more than the first page.
- [ ] **7. Integration test** — Run your test suite against the v2 API endpoint. Verify auth, create, read, update, delete, and list all work with the new formats.
- [ ] **8. Update dependencies** — Ensure any SDKs, client libraries, or generated code target v2.

---

## Upgrade

```bash
zrb update --target v2
```