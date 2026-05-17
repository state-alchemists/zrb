# Migrating from Zrb Task API v1 to v2

Zrb Task API v2 introduces projects, cursor-based pagination, and standard Bearer authentication. These improvements come with **six breaking changes** that require code updates before upgrading. This guide covers each one with before/after examples and a migration checklist.

**If you do nothing else, fix authentication first** — the old `X-Auth-Token` header will return `401` on every request.

---

## Breaking Changes

### 1. Authentication header changed

The custom `X-Auth-Token` header is replaced by a standard `Authorization: Bearer` header. Requests using the old header receive `HTTP 401`.

**Before (v1):**

```
GET /tasks
X-Auth-Token: <your_api_key>
```

**After (v2):**

```
GET /v2/tasks
Authorization: Bearer <your_api_token>
```

### 2. All endpoints are prefixed with `/v2/`

Every endpoint path now starts with `/v2/`. The old unprefixed paths are no longer routed.

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

### 3. Task `id` changed from integer to UUID string

Task identifiers are now UUID strings instead of auto-incrementing integers. Any code that assumes numeric IDs — parsing, sorting, URL construction, database columns — must be updated.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```python
# v1: constructing a URL with an integer ID
url = f"/tasks/{task_id}"
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

```python
# v2: UUIDs are strings — no change to URL construction, but storage/comparison must handle strings
url = f"/v2/tasks/{task_id}"
```

### 4. Task field `done` renamed to `completed`

The boolean field `done` is now `completed`. Sending `done` in a request body is silently ignored (not an error), so watch for tasks that appear unchanged after an update.

**Before (v1):**

```json
{
  "title": "Updated title",
  "done": true
}
```

```python
# v1: reading the field
if task["done"]:
    print("Task is done")
```

**After (v2):**

```json
{
  "title": "Updated title",
  "completed": true
}
```

```python
# v2: use the renamed field
if task["completed"]:
    print("Task is completed")
```

### 5. Task creation now requires `project_id`

v2 introduces projects. Every task must belong to a project, so `project_id` is a required field on creation. Omitting it returns `HTTP 422`.

**Before (v1):**

```json
{
  "title": "New task title"
}
```

**After (v2):**

```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

If your workflow does not use projects, create a default project and use its ID for all tasks.

### 6. List endpoints return a paginated envelope

`GET /v2/tasks` no longer returns a bare array. It returns a paginated envelope with `items`, `total`, and `next_cursor`. Code that treats the response as a direct array will break.

**Before (v1):**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```python
# v1: response IS the list
for task in response.json():
    print(task["title"])
```

**After (v2):**

```json
{
  "items": [
    {"id": "uuid-1", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "uuid-2", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```python
# v2: unwrap the envelope; paginate with cursor
data = response.json()
for task in data["items"]:
    print(task["title"])

# fetch the next page
if data["next_cursor"]:
    next_response = requests.get(f"/v2/tasks?cursor={data['next_cursor']}", headers=headers)
```

Use the `limit` query parameter to control page size (default 20). Pass `?cursor=<next_cursor>` to retrieve subsequent pages. When `next_cursor` is `null`, there are no more results.

---

## Migration Checklist

Work through these steps in order. Each step is independently verifiable.

- [ ] **Update authentication** — Replace `X-Auth-Token` with `Authorization: Bearer`. Confirm by making any v2 request; old auth returns 401.
- [ ] **Prefix all endpoint paths** — Add `/v2/` to every API call. Confirm the old paths return 404.
- [ ] **Update ID handling** — Change ID storage, types, and comparisons from integer to UUID string. Confirm task IDs parse and store correctly.
- [ ] **Rename `done` to `completed`** — Update all reads, writes, and conditionals. Search your codebase for `"done"` in API-related code. Confirm updates actually change task state.
- [ ] **Set up projects and add `project_id`** — Create at least one project. Add `project_id` to every `POST /v2/tasks` call. Confirm creation returns 201 instead of 422.
- [ ] **Adapt list handling to the paginated envelope** — Unwrap `items` from the response. Implement cursor-based pagination if needed. Confirm list views render correctly and existing array-shaped deserialization is removed.

---

## Upgrade

```bash
zrb upgrade --version 2
```