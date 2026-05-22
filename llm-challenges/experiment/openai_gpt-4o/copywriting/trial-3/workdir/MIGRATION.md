# Zrb Task API — v1 to v2 Migration Guide

Zrb v2 introduces projects, paginated list endpoints, UUID-based task IDs, and stricter authentication. This guide catalogues every breaking change and shows exactly what needs to change in your client code.

**Estimated migration time:** 30–60 minutes for a typical codebase.

---

## Breaking Changes at a Glance

| # | Change | Impact |
|---|--------|--------|
| 1 | Auth header: `X-Auth-Token` → `Authorization: Bearer` | All requests rejected with 401 |
| 2 | All endpoints now prefixed with `/v2/` | Existing URLs return 404 |
| 3 | Task `id` type: integer → UUID string | All ID lookups and references break |
| 4 | Field `done` renamed to `completed` | Writes accepted but ignored; reads return new field |
| 5 | `project_id` required on task creation | Requests without it return 422 |
| 6 | List responses: bare array → paginated envelope | Parsing code breaks immediately |

---

## 1. Authentication

The `X-Auth-Token` header has been replaced by the standard `Authorization: Bearer` scheme.

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

Requests using the old header receive HTTP 401 with the message `"Deprecated auth scheme; use Bearer token"`.

---

## 2. Endpoint URL Prefix

All endpoints have moved from `/tasks` to `/v2/tasks`.

**Before (v1):**

```
GET  /tasks
GET  /tasks/{id}
POST /tasks
PUT  /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**

```
GET  /v2/tasks
GET  /v2/tasks/{id}
POST /v2/tasks
PUT  /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

Unprefixed URLs return HTTP 404.

---

## 3. Task `id` Type: Integer → UUID String

Task identifiers are now UUID v4 strings instead of auto-incrementing integers. All references — cache keys, local storage, URLs — must be updated.

**Before (v1):**

```json
{
  "id": 42,
  "title": "My task"
}
```

```javascript
// Client code assumed integers
const taskId = response.data.id;       // 42
fetch(`/tasks/${taskId}`);             // integer in URL
localStorage.setItem("task", taskId);  // stored as integer
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "My task"
}
```

```javascript
// Client code must handle strings
const taskId = response.data.id;            // "a1b2c3d4-..."
fetch(`/v2/tasks/${taskId}`);               // UUID string in URL
localStorage.setItem("task", taskId);       // stored as string
```

**Migration tip:** Run a one-off script to build an integer-to-UUID mapping from v1 data before cutting over, or use the `created_at` timestamp to reconcile records after migration.

---

## 4. Field Rename: `done` → `completed`

The boolean completion field has been renamed.

**Before (v1):**

```json
{
  "title": "Write tests",
  "done": false
}
```

```python
# Client reads the old field
if task["done"]:
    print("Task is complete")
```

**After (v2):**

```json
{
  "title": "Write tests",
  "completed": false
}
```

```python
# Client reads the new field
if task["completed"]:
    print("Task is complete")
```

Similarly, when creating or updating a task:

```diff
- {"title": "Deploy", "done": true}
+ {"title": "Deploy", "completed": true}
```

The v2 API silently ignores the old `done` field — it will not set `completed` from `done`.

---

## 5. Required `project_id` on Task Creation

v2 introduces projects as a first-class entity. Every task must belong to a project.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "project_id": "proj_abc123"}'
```

Omitting `project_id` returns HTTP 422:

```json
{
  "error": "Validation failed",
  "detail": "project_id is required"
}
```

Use the new `GET /v2/projects` endpoint to discover available project IDs.

---

## 6. List Endpoint Response: Bare Array → Paginated Envelope

All list endpoints now return a paginated envelope instead of a bare array.

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

```python
# Client iterated directly over the array
for task in response.json():
    print(task["title"])
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks
```

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false},
    {"id": "c3d4...", "title": "Ship v2", "completed": true}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

```python
# Client must unwrap the envelope
data = response.json()
for task in data["items"]:
    print(task["title"])

# Paginate with the cursor
next_cursor = data.get("next_cursor")
if next_cursor:
    next_page = requests.get("/v2/tasks", params={"cursor": next_cursor}, headers=headers)
```

Optional query parameters:
- `cursor` — pass the value from `next_cursor` to fetch the next page
- `limit` — max results per page (default: 20, max: 100)

---

## Additional Notes

- **Unchanged endpoints:** `DELETE /v2/tasks/{id}` still returns HTTP 204 No Content.
- **Unchanged fields:** `title` and `created_at` keep their v1 semantics.
- **Error responses:** v2 returns standard RFC 7807 problem details for errors.

---

## Migration Checklist

Use this checklist to verify your migration is complete:

- [ ] **Auth header** — Replace all `X-Auth-Token` headers with `Authorization: Bearer` tokens.
- [ ] **Endpoint prefix** — Update all API URLs from `/tasks` to `/v2/tasks`.
- [ ] **Task IDs** — Change `id` handling from integer to UUID string. Update database schemas, cache keys, and local storage.
- [ ] **Field rename** — Replace all references to `done` with `completed` in reads, creates, and updates.
- [ ] **Project assignment** — Add `project_id` to all task creation requests. Migrate existing tasks to a default project if needed.
- [ ] **List parsing** — Update list-response parsers to unwrap the `items` envelope. Add pagination logic using `next_cursor`.
- [ ] **Test** — Run your test suite against a v2 sandbox environment. Verify every endpoint returns the expected status code and shape.

---

## Upgrade

Install or update to the latest Zrb CLI:

```bash
pip install --upgrade zrb
```

To verify:

```bash
zrb --version
# Should print: zrb 2.x.x
```

**Rollback:** Zrb v2 API is deployed alongside a v1 compatibility layer for 90 days. During this period, `X-Auth-Token` auth and `/tasks` endpoints will continue to work but log deprecation warnings. Use the checklist above to migrate before the compatibility window closes.
