# Zrb CLI v1 → v2 Migration Guide

v2 introduces projects as a first-class concept, stricter authentication, paginated
list endpoints, and several field renames. This guide covers every breaking change
and walks you through the migration step by step.

---

## Breaking Changes Overview

| # | Change | Impact |
|---|--------|--------|
| 1 | Endpoints prefixed with `/v2/` | All URL strings need updating |
| 2 | Auth header changed from `X-Auth-Token` to `Authorization: Bearer` | Every request must use the new header |
| 3 | Task `id` type: integer → UUID string | ID comparisons, caching, and URL construction break |
| 4 | Field `done` renamed to `completed` | Read and write payloads must use the new field name |
| 5 | `project_id` required when creating tasks | Create-task payloads need a new required field |
| 6 | List endpoints return a paginated envelope | Response parsing code must unwrap `.items` and handle cursors |

---

## 1. Endpoint Prefix — `/v2/`

**What changed:** All endpoints are now mounted under `/v2/`.

**Before (v1):**

```
GET /tasks
POST /tasks
GET /tasks/42
```

**After (v2):**

```
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Action:** Prepend `/v2` to every endpoint path in your HTTP client configuration.
If you have a base URL constant, update it once:

```python
# v1
BASE_URL = "https://api.zrb.dev"

# v2
BASE_URL = "https://api.zrb.dev/v2"
```

---

## 2. Authentication — Bearer Token

**What changed:** The `X-Auth-Token` header is replaced with a standard
`Authorization: Bearer` header. v1-style requests return HTTP 401.

**Before (v1):**

```
X-Auth-Token: abc123
```

**After (v2):**

```
Authorization: Bearer abc123
```

**Action:** Replace your auth-header injection logic. Example with curl:

```bash
# v1
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks

# v2
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

Example with JavaScript `fetch`:

```javascript
// v1
fetch("/tasks", { headers: { "X-Auth-Token": token } })

// v2
fetch("/v2/tasks", { headers: { "Authorization": `Bearer ${token}` } })
```

---

## 3. Task ID — Integer → UUID String

**What changed:** `id` is now a UUID string (e.g., `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`)
instead of an auto-incrementing integer. Any code that relies on integer IDs —
comparisons, type checks, URL construction, cache keys — will break.

**Before (v1):**

```json
{ "id": 42, "title": "Write tests", "done": false }
```

**After (v2):**

```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false }
```

**Action:**

- Update any type annotations from `int` to `str` (or `string`).
- Replace integer-based cache keys or lookup tables with string-based ones.
- If you store IDs in a database, widen the column to accommodate UUIDs.
- Remove any assumption about sequential IDs (e.g., `id == id + 1`).

```python
# v1 — won't work in v2
if task["id"] == 42:

# v2
if task["id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890":
```

---

## 4. Field Rename — `done` → `completed`

**What changed:** The boolean task-status field is now `completed` instead of `done`.
Both reading and writing use the new name.

**Before (v1):**

```json
{ "done": true }
```

**After (v2):**

```json
{ "completed": true }
```

**Action:** Rename all references in your codebase. Watch for both reads (response parsing)
and writes (request bodies).

```python
# v1 — read
if task["done"]:
    print("Task is complete")

# v2 — read
if task["completed"]:
    print("Task is complete")
```

```python
# v1 — write
requests.put(url, json={"done": True})

# v2 — write
requests.put(url, json={"completed": True})
```

---

## 5. New Required Field — `project_id`

**What changed:** Creating a task now requires a `project_id` string. Omitting it
returns HTTP 422.

**Before (v1):**

```json
POST /tasks
{ "title": "New task" }
```

**After (v2):**

```json
POST /v2/tasks
{ "title": "New task", "project_id": "proj_abc123" }
```

**Action:**

1. Obtain a valid `project_id`. The v2 API likely exposes a `/v2/projects` endpoint
   (refer to the full v2 API reference).
2. Add `project_id` to every create-task call in your code.

```python
# v1
payload = {"title": "Fix login bug"}

# v2
payload = {"title": "Fix login bug", "project_id": "proj_abc123"}
```

If your application allows users to create tasks without selecting a project,
add project assignment logic to your UI or workflow layer before upgrading.

---

## 6. List Endpoints — Paginated Envelope

**What changed:** List endpoints no longer return a bare array. Instead they return
a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**

```json
GET /tasks
[
  { "id": 1, "title": "Buy milk", "done": false },
  { "id": 2, "title": "Ship v1", "done": true }
]
```

**After (v2):**

```json
GET /v2/tasks
{
  "items": [
    { "id": "a1b2c3d4-...", "title": "Buy milk", "completed": false },
    { "id": "e5f6a7b8-...", "title": "Ship v1", "completed": true }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Action:**

- Always unwrap `.items` from the response envelope.
- Use `?cursor=<next_cursor>&limit=<n>` to fetch subsequent pages.
- The `total` field reflects the full result count across all pages.

```python
# v1 — parse
tasks = response.json()

# v2 — parse
data = response.json()
tasks = data["items"]
total = data["total"]

# v2 — paginate
while data["next_cursor"]:
    resp = session.get(url, params={"cursor": data["next_cursor"]})
    data = resp.json()
    tasks.extend(data["items"])
```

The default page size is 20. Pass `?limit=100` to adjust (subject to server cap).

---

## Migration Checklist

Use this checklist to track your progress. Tick off each item as you complete it.

- [ ] **1. Endpoint prefix** — Prepend `/v2` to all API paths in your client config.
- [ ] **2. Auth header** — Replace `X-Auth-Token` with `Authorization: Bearer`.
- [ ] **3. Task ID type** — Update type annotations, cache keys, and database schemas
      from `int` to `string`/`UUID`. Remove sequential-ID assumptions.
- [ ] **4. Field rename** — Replace all references to `done` with `completed` in
      read and write code paths.
- [ ] **5. Required `project_id`** — Add `project_id` to every create-task payload.
      Update UI/UX if users no longer create tasks without a project context.
- [ ] **6. Pagination** — Unwrap `.items` from list responses. Implement cursor-based
      pagination where you fetch more than one page.
- [ ] **7. Stale data** — If you cache or persist task IDs from v1, migrate them or
      rebuild your data store. v1 integer IDs are incompatible with v2 UUIDs.
- [ ] **8. Test** — Run your test suite against the v2 API. Verify create, read,
      update, delete, and list operations with the new payload shapes.

---

## Upgrade

Once your code is ready, install the v2 SDK or update your dependency:

```bash
pip install --upgrade zrb-cli
```

Or if you use the container image:

```bash
docker pull zrb/cli:2
```

Verify the installation:

```bash
zrb --version
# Expected: zrb 2.x.x
```

If you encounter issues during migration, open a discussion at
[github.com/state-alchemists/zrb/discussions](https://github.com/state-alchemists/zrb/discussions).
