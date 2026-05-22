# Zrb CLI v2 Migration Guide

This guide covers every breaking change between Zrb v1 and v2. Read it top to bottom, then follow the checklist at the end.

---

## Table of Contents

- [Breaking Change 1: Authentication Header Changed](#breaking-change-1-authentication-header-changed)
- [Breaking Change 2: All Endpoints Now Prefixed with `/v2/`](#breaking-change-2-all-endpoints-now-prefixed-with-v2)
- [Breaking Change 3: Task `id` Is Now a UUID String](#breaking-change-3-task-id-is-now-a-uuid-string)
- [Breaking Change 4: Field `done` Renamed to `completed`](#breaking-change-4-field-done-renamed-to-completed)
- [Breaking Change 5: `project_id` Required When Creating a Task](#breaking-change-5-project_id-required-when-creating-a-task)
- [Breaking Change 6: List Endpoints Return a Paginated Envelope](#breaking-change-6-list-endpoints-return-a-paginated-envelope)
- [Step-by-Step Migration Checklist](#step-by-step-migration-checklist)
- [Upgrade](#upgrade)

---

## Breaking Change 1: Authentication Header Changed

**v1** used a custom `X-Auth-Token` header. **v2** uses the standard `Authorization: Bearer` scheme. Requests using the old header receive HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

**Action:** Update every HTTP call to send `Authorization: Bearer <token>` instead of `X-Auth-Token: <key>`. No token value migration is needed — your existing key works as the Bearer token.

---

## Breaking Change 2: All Endpoints Now Prefixed with `/v2/`

All routes moved from `/tasks` to `/v2/tasks`. Requests to the old paths receive HTTP 404.

| Operation   | v1 Endpoint         | v2 Endpoint             |
|-------------|---------------------|-------------------------|
| List tasks  | `GET /tasks`        | `GET /v2/tasks`         |
| Get task    | `GET /tasks/{id}`   | `GET /v2/tasks/{id}`    |
| Create task | `POST /tasks`       | `POST /v2/tasks`        |
| Update task | `PUT /tasks/{id}`   | `PUT /v2/tasks/{id}`    |
| Delete task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**Before (v1):**

```python
import requests

resp = requests.post(
    "https://api.zrb.dev/tasks",
    headers={"X-Auth-Token": token},
    json={"title": "Write tests"},
)
```

**After (v2):**

```python
import requests

resp = requests.post(
    "https://api.zrb.dev/v2/tasks",
    headers={"Authorization": f"Bearer {token}"},
    json={"title": "Write tests", "project_id": "proj_abc123"},
)
```

**Action:** Prefix all API paths with `/v2/`.

---

## Breaking Change 3: Task `id` Is Now a UUID String

Task identifiers changed from auto-incrementing integers to UUID v4 strings. Existing integer IDs are **not** migrated; v2 assigned fresh UUIDs to all tasks. You must re-resolve any hardcoded or stored integer IDs.

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

**Action:**
- Update any schemas, type definitions, or database columns that store task IDs from `integer` to `string` (UUID).
- Remove code that relies on sequential IDs (e.g., auto-increment assumptions, ID-range queries).
- Re-fetch references if you previously stored integer IDs in other systems.

---

## Breaking Change 4: Field `done` Renamed to `completed`

The boolean field that tracks task completion was renamed. The old `done` field is absent from v2 responses; sending `done` in a request is ignored or may cause a validation error depending on strictness mode.

**Before (v1) — reading a task:**

```javascript
// v1
fetch("https://api.zrb.dev/tasks/42", {
  headers: { "X-Auth-Token": token },
})
  .then((r) => r.json())
  .then((task) => console.log(task.done)); // false
```

**After (v2) — reading a task:**

```javascript
// v2
fetch("https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890", {
  headers: { "Authorization": `Bearer ${token}` },
})
  .then((r) => r.json())
  .then((task) => console.log(task.completed)); // false
```

**Before (v1) — updating a task:**

```bash
curl -X PUT https://api.zrb.dev/tasks/42 \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"done": true}'
```

**After (v2) — updating a task:**

```bash
curl -X PUT https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

**Action:** Search your codebase for `.done` on task objects and replace with `.completed`. Update any UI components that read or write this field.

---

## Breaking Change 5: `project_id` Required When Creating a Task

v1 allowed creating tasks with only a `title`. v2 requires a `project_id` in the request body. Omitting it returns HTTP 422 Unprocessable Entity.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

**Action:**
- Decide how to assign projects in your application flow.
- Update task-creation forms, scripts, and API calls to prompt for or derive a `project_id`.
- Retrieve available projects via the (forthcoming) projects endpoint, or use a default project ID if your workflow is single-project.

---

## Breaking Change 6: List Endpoints Return a Paginated Envelope

v1 returned a bare JSON array. v2 returns a paginated envelope with `items`, `total`, and `next_cursor`. Clients that assume `response.data` is an array will break.

**Before (v1):**

```python
import requests

resp = requests.get(
    "https://api.zrb.dev/tasks",
    headers={"X-Auth-Token": token},
)
tasks = resp.json()           # bare array — works in v1
for task in tasks:
    print(task["title"])
```

**After (v2):**

```python
import requests

resp = requests.get(
    "https://api.zrb.dev/v2/tasks",
    headers={"Authorization": f"Bearer {token}"},
)
body = resp.json()
tasks = body["items"]         # wrapped in envelope
total = body["total"]         # total matching items
next_cursor = body.get("next_cursor")  # None if last page

for task in tasks:
    print(task["title"])

# Paginate
while next_cursor:
    resp = requests.get(
        "https://api.zrb.dev/v2/tasks",
        headers={"Authorization": f"Bearer {token}"},
        params={"cursor": next_cursor, "limit": 20},
    )
    body = resp.json()
    tasks = body["items"]
    next_cursor = body.get("next_cursor")
    for task in tasks:
        print(task["title"])
```

**Action:**
- Unwrap list responses through `body["items"]` instead of consuming `body` directly.
- If you paginate, wire up cursor-based pagination using `next_cursor` and the `?cursor=` query parameter.
- Optionally use `?limit=` to control page size (default 20).

---

## Step-by-Step Migration Checklist

- [ ] **Update authentication.** Replace `X-Auth-Token` with `Authorization: Bearer` in every client.
- [ ] **Prefix endpoints with `/v2/`.** Change all route paths from `/tasks` to `/v2/tasks`.
- [ ] **Migrate task IDs.** Update schemas, database columns, and stored references from integer to UUID string. Re-fetch any hardcoded IDs.
- [ ] **Rename `done` to `completed`.** Update all read and write code that touches the completion status field.
- [ ] **Add `project_id` to task creation.** Identify how your app will supply a project ID and update all `POST /v2/tasks` call sites.
- [ ] **Update list-response handling.** Unwrap responses through the `items` key and implement cursor-based pagination if you display more than 20 tasks.
- [ ] **Run your test suite.** Verify every endpoint against v2. Pay special attention to Create (422 on missing `project_id`) and List (envelope shape).

---

## Upgrade

Install Zrb CLI v2 and verify the installation:

```bash
pip install --upgrade zrb
zrb --version
# → zrb 2.x.x
```

That's it. Follow the checklist above, and your codebase will be ready for v2.
