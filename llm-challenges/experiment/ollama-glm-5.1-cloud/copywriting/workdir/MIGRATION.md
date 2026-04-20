# Zrb Task API — Migrating from v1 to v2

v2 introduces projects, cursor-based pagination, and stricter authentication. This guide covers **every breaking change** you need to address before upgrading.

---

## Breaking Changes

### 1. Authentication Header Changed

The `X-Auth-Token` header is **no longer accepted**. Requests using it will receive **HTTP 401**. You must switch to the standard `Authorization: Bearer` header.

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

### 2. All Endpoints Prefixed with `/v2/`

Every endpoint path now starts with `/v2/`. Requests to the old paths (e.g. `/tasks`) will fail.

**Before (v1):**

```
GET    /tasks
GET    /tasks/{id}
POST   /tasks
PUT    /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**

```
GET    /v2/tasks
GET    /v2/tasks/{id}
POST   /v2/tasks
PUT    /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

### 3. Task `id` Changed from Integer to UUID String

Task IDs are now UUID strings instead of integers. Any code that parses, stores, or validates IDs as integers will break.

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

Update your models and database columns accordingly. URL references to tasks also change:

**Before (v1):**

```
GET /tasks/42
```

**After (v2):**

```
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 4. Field `done` Renamed to `completed`

The boolean field `done` has been renamed to `completed`. This affects both task responses and update request bodies.

**Before (v1) — reading:**

```python
if task["done"]:
    print("Task finished!")
```

**After (v2) — reading:**

```python
if task["completed"]:
    print("Task finished!")
```

**Before (v1) — updating:**

```json
PUT /tasks/42
{
  "done": true
}
```

**After (v2) — updating:**

```json
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
{
  "completed": true
}
```

Sending `done` in a v2 request will be silently ignored or cause unexpected behavior — it will not set the completed state.

### 5. Task Creation Now Requires `project_id`

Creating a task without `project_id` now returns **HTTP 422 Unprocessable Entity**. You must include a `project_id` in every `POST /v2/tasks` request.

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

### 6. List Endpoints Return a Paginated Envelope

`GET /v2/tasks` no longer returns a bare JSON array. It now returns a paginated envelope with `items`, `total`, and `next_cursor`. Any code that iterates over the response as a plain array will break.

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
    {"id": "uuid-1", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "uuid-2", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch subsequent pages, pass the cursor as a query parameter:

```
GET /v2/tasks?cursor=cursor_xyz
```

You can also control page size with `?limit=N` (default 20).

**Before (v1) — consuming the list:**

```python
tasks = requests.get("/tasks", headers={"X-Auth-Token": key}).json()
for task in tasks:
    print(task["title"], task["done"])
```

**After (v2) — consuming the list:**

```python
response = requests.get(
    "/v2/tasks",
    headers={"Authorization": f"Bearer {token}"},
).json()
for task in response["items"]:
    print(task["title"], task["completed"])
# Fetch next page
if response["next_cursor"]:
    next_page = requests.get(
        f"/v2/tasks?cursor={response['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
```

---

## Migration Checklist

1. **Update authentication** — Replace all `X-Auth-Token` headers with `Authorization: Bearer <token>`.
2. **Update all endpoint URLs** — Add the `/v2/` prefix to every request path.
3. **Change ID handling** — Update models, schemas, database columns, and URL builders to use UUID strings instead of integers.
4. **Rename `done` → `completed`** — Update all reads, writes, filters, and assertions that reference the `done` field.
5. **Add `project_id` to task creation** — Ensure every `POST /v2/tasks` request includes a `project_id`.
6. **Parse the paginated envelope** — Update all list-consumption code to read from the `items` key instead of treating the response as a bare array. Implement cursor-based pagination if you need to fetch more than one page of results.
7. **Test all integrations end-to-end** — Run your test suite against a v2 instance before deploying.

---

Upgrade now:

```
zrb upgrade --to v2
```