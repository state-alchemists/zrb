# Zrb Task API — Migrating from v1 to v2

This guide covers everything you need to migrate your integration from the v1 API to v2. It assumes you are familiar with v1 and focuses exclusively on breaking changes.

---

## Breaking Changes Overview

| # | Change | Impact |
|---|--------|--------|
| 1 | All endpoints prefixed with `/v2/` | Every URL must be updated |
| 2 | Auth header changed from `X-Auth-Token` to `Authorization: Bearer` | Old header returns 401 |
| 3 | Task `id` changed from integer to UUID string | Code expecting integers will break |
| 4 | Task field `done` renamed to `completed` | Read and write paths both affected |
| 5 | Task creation now requires `project_id` | POST without `project_id` returns 422 |
| 6 | List endpoints return paginated envelope instead of bare array | Code iterating the response directly will break |

---

## 1. Endpoint Prefix

All endpoints now live under `/v2/`. Requests to the old paths will 404.

**Before**
```
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After**
```
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication Header

The `X-Auth-Token` header is no longer accepted. Requests using it receive **HTTP 401**. Replace it with a standard `Authorization: Bearer` header.

**Before**
```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.io/tasks
```

**After**
```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.io/v2/tasks
```

---

## 3. Task `id` Type: Integer → UUID String

Task IDs are now UUID strings instead of auto-incrementing integers. Any code that parses, stores, or validates IDs as integers must be updated.

**Before**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Typical code change — Python:**

```python
# Before
task_id: int = task["id"]

# After
task_id: str = task["id"]
```

**Typical code change — database schema:**

```sql
-- Before
id  INTEGER PRIMARY KEY

-- After
id  TEXT PRIMARY KEY
```

---

## 4. Field Rename: `done` → `completed`

Both reading and writing the task status field must use `completed` instead of `done`. Sending `done` in a request body will be silently ignored.

**Before**
```json
{ "done": true }
```

**After**
```json
{ "completed": true }
```

**Typical code change — Python:**

```python
# Before
if task["done"]:
    ...

# After
if task["completed"]:
    ...
```

```python
# Before (update)
requests.put(url, json={"done": True})

# After (update)
requests.put(url, json={"completed": True})
```

---

## 5. Required `project_id` on Task Creation

`POST /v2/tasks` now requires a `project_id` field. Omitting it returns **HTTP 422** with a validation error. You must associate every task with a project.

**Before**
```json
{
  "title": "New task title"
}
```

**After**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Typical code change — Python:**

```python
# Before
requests.post(url, json={"title": "New task title"})

# After
requests.post(url, json={
    "title": "New task title",
    "project_id": "proj_abc123",
})
```

---

## 6. Paginated List Response

`GET /v2/tasks` no longer returns a bare array. It returns a paginated envelope with `items`, `total`, and `next_cursor`. Code that iterates the response directly will break.

**Before**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After**
```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "e5f67890-...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, pass the cursor as a query parameter:

```
GET /v2/tasks?cursor=cursor_xyz
```

You can also set the page size with `limit` (default 20):

```
GET /v2/tasks?limit=50&cursor=cursor_xyz
```

**Typical code change — Python:**

```python
# Before
tasks = requests.get(url).json()
for task in tasks:
    ...

# After
resp = requests.get(url).json()
for task in resp["items"]:
    ...

# To paginate through all results:
cursor = None
while True:
    params = {}
    if cursor:
        params["cursor"] = cursor
    resp = requests.get(url, params=params).json()
    for task in resp["items"]:
        ...
    cursor = resp.get("next_cursor")
    if not cursor:
        break
```

---

## Migration Checklist

Work through these steps in order. Each step is independent, but tackling them top-to-bottom minimizes the time your integration is broken.

- [ ] **Update all endpoint URLs** — add the `/v2/` prefix to every request path.
- [ ] **Switch the auth header** — replace `X-Auth-Token` with `Authorization: Bearer`. Remove any code that sets or reads `X-Auth-Token`.
- [ ] **Update ID handling** — change type annotations, database columns, and validation logic from integer to UUID string.
- [ ] **Rename `done` to `completed`** — update both read paths (e.g., `task["done"]` → `task["completed"]`) and write paths (e.g., request bodies).
- [ ] **Add `project_id` to task creation** — include a valid `project_id` in every `POST /v2/tasks` request body. Handle 422 errors if the project does not exist.
- [ ] **Adapt to the paginated envelope** — update list-response parsing to read from the `items` key. Implement cursor-based pagination if you need more than the first page.
- [ ] **Run your test suite** — verify every endpoint and edge case against the v2 API.
- [ ] **Remove dead code** — clean up any v1-specific workarounds, fallback headers, or integer-ID assumptions.

---

## Upgrade

```bash
npm install zrb@2
```