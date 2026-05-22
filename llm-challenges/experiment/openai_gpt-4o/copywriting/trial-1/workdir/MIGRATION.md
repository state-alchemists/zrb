# Zrb CLI v1 → v2 Migration Guide

**Audience:** Developers currently using Zrb CLI v1  
**Goal:** Upgrade your integrations from v1 to v2 with minimal disruption

---

## Overview

v2 introduces projects, pagination, and stricter authentication. Six breaking changes affect every API consumer. Each change is isolated and mechanical — plan for an afternoon, not a sprint.

**Breaking changes at a glance:**

| # | Area | v1 | v2 |
|---|------|----|----|
| 1 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 2 | Authentication | `X-Auth-Token` header | `Authorization: Bearer` header |
| 3 | Task ID type | Integer | UUID string |
| 4 | Task status field | `done` | `completed` |
| 5 | Task creation | `title` only | `title` + `project_id` (required) |
| 6 | List response | Bare array | Paginated envelope |

---

## 1. Endpoint Prefix — `/v2/` is now required

All endpoints are mounted under `/v2/`. Requests to the bare `/tasks` path will not route.

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks
```

| Endpoint | v1 | v2 |
|----------|----|----|
| List Tasks | `GET /tasks` | `GET /v2/tasks` |
| Get Task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create Task | `POST /tasks` | `POST /v2/tasks` |
| Update Task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete Task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

---

## 2. Authentication — Bearer token replaces API key header

The `X-Auth-Token` header is no longer accepted. Use a standard `Authorization: Bearer` header instead. Requests using the old header receive HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: sk-abc123" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer zrb_v2_abc123" https://api.zrb.dev/v2/tasks
```

---

## 3. Task ID — Integer replaced by UUID string

Task identifiers are now UUID strings (v4). You cannot pass the old integer IDs to v2 endpoints. If your system stores persisted task IDs, you will need to re-fetch or migrate the mappings.

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

**Impact on requests:**

```bash
# v1 — integer ID
curl https://api.zrb.dev/tasks/42

# v2 — UUID string ID
curl https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 4. Field Rename — `done` is now `completed`

The boolean task status field has been renamed. v2 does not accept `done` on write, nor does it return it on read.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Ship v1",
  "done": true
}
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v1",
  "completed": true
}
```

**Updating a task (before → after):**

```bash
# v1
curl -X PUT https://api.zrb.dev/tasks/42 \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: sk-abc123" \
  -d '{"done": true}'

# v2
curl -X PUT https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer zrb_v2_abc123" \
  -d '{"completed": true}'
```

---

## 5. Task Creation — `project_id` is now required

Every task must belong to a project. The `project_id` field is mandatory on `POST /v2/tasks`. Omitting it returns HTTP 422 with a validation error.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Write tests"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer zrb_v2_abc123" \
  -d '{"title": "Write tests", "project_id": "proj_abc123"}'
```

> **Migration note:** You will need to create or identify a project before creating tasks. See the [Projects API reference](https://api.zrb.dev/v2/docs) for available endpoints.

---

## 6. List Response — Bare array replaced by paginated envelope

List endpoints no longer return a raw JSON array. All collection responses are wrapped in a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1) — bare array:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) — paginated envelope:**

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

**Consuming paginated results:**

```bash
# First page
curl -H "Authorization: Bearer zrb_v2_abc123" \
  "https://api.zrb.dev/v2/tasks?limit=20"

# Next page (use next_cursor from previous response)
curl -H "Authorization: Bearer zrb_v2_abc123" \
  "https://api.zrb.dev/v2/tasks?limit=20&cursor=cursor_xyz"
```

The default page size is 20. You can adjust this with the `limit` query parameter (max 100).

**Updating client code:**

```python
# v1 — bare array, no pagination
response = requests.get("https://api.zrb.dev/tasks")
tasks = response.json()  # list of dicts

# v2 — paginated envelope
response = requests.get(
    "https://api.zrb.dev/v2/tasks",
    headers={"Authorization": "Bearer zrb_v2_abc123"},
    params={"limit": 100}
)
body = response.json()
tasks = body["items"]        # list of dicts
total = body["total"]        # int
cursor = body["next_cursor"] # str or None
```

---

## Step-by-Step Migration Checklist

Use this checklist to track your progress. Tick each item off as you go.

- [ ] **1. Update authentication**
      Replace every instance of `X-Auth-Token: <key>` with `Authorization: Bearer <token>`. Obtain a v2-compatible token from your account dashboard.

- [ ] **2. Prefix all endpoint URLs with `/v2/`**
      Audit every API call. `GET /tasks` → `GET /v2/tasks`, `POST /tasks` → `POST /v2/tasks`, etc.

- [ ] **3. Refresh persisted task ID mappings**
      If your database or cache stores integer task IDs, re-fetch the task list from v2 to build a UUID → metadata mapping. The old integers have no meaning in v2.

- [ ] **4. Rename `done` to `completed` everywhere**
      Search your codebase for `"done"` and `'done'` in request bodies and response parsers. Update serializers, schemas, type definitions, and UI components.

- [ ] **5. Add `project_id` to task creation**
      Identify which project each new task belongs to. Add `project_id` to every `POST /v2/tasks` request body. Handle HTTP 422 responses gracefully during the transition.

- [ ] **6. Migrate list-response consumers to the paginated envelope**
      Update code that reads list responses to extract `items` from the envelope. If you fetch all tasks, implement cursor-based pagination by following `next_cursor` until it is `null`.

- [ ] **7. Run integration tests**
      Execute your full test suite against v2. Pay special attention to authentication errors (401), validation errors (422), and pagination edge cases (empty list, single page, multiple pages).

- [ ] **8. Deploy and monitor**
      Deploy the updated client code. Monitor for 401, 404, and 422 responses in your logs for the first hour after deployment.

---

## Upgrade Command

Run the following to upgrade the Zrb CLI itself:

```bash
pip install --upgrade zrb
```

Verify the installation:

```bash
zrb --version
# Expected: v2.x.x
```

> **Questions or issues?** Open a GitHub Discussion at [github.com/state-alchemists/zrb/discussions](https://github.com/state-alchemists/zrb/discussions) or refer to the full [v2 API Reference](v2_spec.md).
