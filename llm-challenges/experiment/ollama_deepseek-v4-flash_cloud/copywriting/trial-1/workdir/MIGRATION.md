# Migrating from Zrb Task API v1 to v2

Zrb Task API v2 introduces projects, pagination, and stricter security. This guide covers every breaking change and walks you through upgrading your existing integrations.

All endpoint paths, request bodies, and response shapes have changed. There is no backward-compatible mode — you must update both your client code and any persisted task references.

---

## Breaking Changes at a Glance

| # | Change | Impact |
|---|--------|--------|
| 1 | Endpoint prefix changed | All requests must target `/v2/tasks` instead of `/tasks` |
| 2 | Auth header changed | `X-Auth-Token` → `Authorization: Bearer` — old header returns 401 |
| 3 | Task `id` is now a UUID string | Integer IDs no longer valid; existing IDs are **not** preserved |
| 4 | `done` renamed to `completed` | Any code reading or writing `done` will silently break |
| 5 | `project_id` is required on creation | `POST /v2/tasks` returns 422 if omitted |
| 6 | List endpoints return a paginated envelope | Bare arrays replaced by `{items, total, next_cursor}` |

---

## 1. Endpoint Prefix

All v2 endpoints live under `/v2/`. Requests to the old `/tasks` path return 404.

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks
```

```python
response = requests.get("https://api.zrb.dev/tasks")
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks
```

```python
response = requests.get("https://api.zrb.dev/v2/tasks")
```

---

## 2. Authentication Header

The `X-Auth-Token` header is replaced with the standard `Authorization: Bearer` scheme. Requests using the old header receive HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

```python
headers = {"X-Auth-Token": "abc123"}
```

**After (v2):**

```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

```python
headers = {"Authorization": "Bearer abc123"}
```

---

## 3. Task ID: Integer → UUID String

Task identifiers are now UUID version 4 strings. Integer IDs from v1 are **not** migrated — you must re-resolve any references (e.g., stored IDs in databases, bookmarked URLs, or cached task lists).

**Before (v1):**

```json
{"id": 42, "title": "Write tests", "done": false}
```

```bash
curl https://api.zrb.dev/tasks/42
```

**After (v2):**

```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false}
```

```bash
curl https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 4. Field Rename: `done` → `completed`

The task status field is renamed. v2 ignores `done` entirely — reading it always returns `undefined` / `null`, and writing it has no effect.

**Before (v1):**

```json
{"id": 1, "title": "Ship v1", "done": true}
```

```python
# Reading
if task["done"]:
    print("Task is complete")

# Writing
payload = {"done": True}
```

**After (v2):**

```json
{"id": "a1b2c3d4-...", "title": "Ship v1", "completed": true}
```

```python
# Reading
if task["completed"]:
    print("Task is complete")

# Writing
payload = {"completed": True}
```

---

## 5. `project_id` Required on Creation

Every task must belong to a project. The `project_id` field is required in `POST /v2/tasks`; omitting it returns HTTP 422.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: abc123" \
  -d '{"title": "Write tests"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer abc123" \
  -d '{"title": "Write tests", "project_id": "proj_abc123"}'
```

```python
payload = {"title": "Write tests", "project_id": "proj_abc123"}
response = requests.post(
    "https://api.zrb.dev/v2/tasks",
    headers={"Authorization": "Bearer abc123"},
    json=payload,
)
```

---

## 6. List Response: Bare Array → Paginated Envelope

`GET /tasks` previously returned a bare JSON array. `GET /v2/tasks` returns a paginated envelope with cursor-based navigation.

**Before (v1):**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```python
tasks = response.json()  # list of tasks
for t in tasks:
    print(t["title"])
```

**After (v2):**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "c3d4...", "title": "Ship v1", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```python
body = response.json()
tasks = body["items"]       # list of tasks
total = body["total"]       # total matching records
next_cursor = body.get("next_cursor")  # None if last page

# Fetch the next page
if next_cursor:
    next_page = requests.get(
        "https://api.zrb.dev/v2/tasks",
        params={"cursor": next_cursor, "limit": 20},
        headers={"Authorization": "Bearer abc123"},
    )
```

Query parameters `cursor` and `limit` (default 20) control pagination.

---

## Step-by-Step Migration Checklist

1. **Update base URL** — Replace `https://api.zrb.dev/tasks` with `https://api.zrb.dev/v2/tasks` in all clients.
2. **Replace auth header** — Change `X-Auth-Token` to `Authorization: Bearer` in every request.
3. **Re-resolve task IDs** — Any integer task IDs stored externally (database, URLs, cache) must be replaced with the new UUIDs. Re-fetch your task list from v2, or re-import data if your backend provides a migration endpoint.
4. **Rename `done` → `completed`** — Audit every read and write of the task status field in your codebase.
5. **Add `project_id` to task creation** — Identify what project a new task belongs to and include `project_id` in every `POST` body.
6. **Update list-response parsing** — Change any code that reads a bare array from `GET /tasks` to read `response["items"]` from the paginated envelope. Add cursor-based pagination if you need to fetch all records.
7. **Test all CRUD operations** — Run your test suite against the v2 API. Pay special attention to 401 (bad auth), 404 (wrong path or UUID), and 422 (missing `project_id`) responses.
8. **Verify pagination** — Confirm your client correctly handles multi-page results and terminates when `next_cursor` is absent.

---

## Upgrade Command

```bash
pip install --upgrade zrb-cli
```

After upgrading, update your API client code according to the checklist above. The v1 API is deprecated and will be decommissioned 90 days after this release.
