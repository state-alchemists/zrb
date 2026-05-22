# Zrb CLI v1 → v2 Migration Guide

**Audience:** Developers migrating existing v1 integrations.
**Last updated:** 2026-05-22

---

## Overview

Zrb CLI v2 introduces projects, paginated list endpoints, and stricter authentication. Six breaking changes affect every existing integration. Each is documented below with the exact migration steps.

---

## Breaking Changes

### 1. Endpoint Path — `/v2/` Prefix

All resource paths now live under `/v2/`.

**v1 (before):**

```bash
curl https://api.zrb.dev/tasks
```

**v2 (after):**

```bash
curl https://api.zrb.dev/v2/tasks
```

**Impact:** Update every URL your code references against the API.

---

### 2. Authentication — Bearer Token Replaces `X-Auth-Token`

The custom `X-Auth-Token` header has been replaced by the standard `Authorization: Bearer` header. Requests using the old header receive HTTP 401.

**v1 (before):**

```bash
curl -H "X-Auth-Token: sk-abc123" https://api.zrb.dev/tasks
```

**v2 (after):**

```bash
curl -H "Authorization: Bearer sk-abc123" https://api.zrb.dev/v2/tasks
```

**Impact:** Update all client — server-side, SDK, cURL, Postman — to use the Bearer scheme.

---

### 3. Task `id` — Integer → UUID String

Task identifiers have changed from auto-incrementing integers to UUID v4 strings.

**v1 (before):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**v2 (after):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123"
}
```

**Impact:**
- Local state that assumes integer IDs (e.g., sequential lookup, comparison, type checks) must be updated to handle strings.
- Any stored integer IDs from v1 cannot be reused — re-fetch or migrate them before adopting v2 endpoints.

**Bad pattern to fix:**

```python
# v1 — breaks on v2 UUID strings
if task["id"] > 0:
    ...
```

**v2-compatible:**

```python
if task["id"]:
    ...
```

---

### 4. Field Rename — `done` → `completed`

The boolean completion field has been renamed. Sending `done` in a v2 request body is silently ignored — it will not update the task status.

**v1 (before):**

```python
response = requests.put(f"{base}/tasks/{id}", json={
    "title": "Updated title",
    "done": True
})
```

**v2 (after):**

```python
response = requests.put(f"{base}/v2/tasks/{id}", json={
    "title": "Updated title",
    "completed": True
})
```

**Impact:** Search your codebase for every read and write of the `done` key in task objects and rename to `completed`.

---

### 5. New Required Field — `project_id` on Creation

Creating a task now requires a `project_id`. Requests that omit it return HTTP 422.

**v1 (before):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "Authorization: Bearer sk-abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk"}'
```

**v2 (after):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer sk-abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "project_id": "proj_abc123"}'
```

**Impact:** You now need a project to create tasks. List available projects, store the target `project_id`, and pass it on every `POST /v2/tasks` call.

---

### 6. List Response — Bare Array → Paginated Envelope

List endpoints no longer return a flat array. They return an envelope with `items`, `total`, and a `next_cursor` for pagination.

**v1 (before) — bare array:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**v2 (after) — paginated envelope:**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b3c4...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**v1 code that will break:**

```python
tasks = response.json()        # was a list
for task in tasks:              # was fine
    print(task["title"])
```

**v2-compatible:**

```python
body = response.json()
tasks = body["items"]           # now nested under "items"
total = body["total"]           # pagination metadata
cursor = body["next_cursor"]    # None on last page
for task in tasks:
    print(task["title"])
```

**Fetching subsequent pages:**

```
GET /v2/tasks?cursor=cursor_xyz&limit=20
```

---

## Migration Checklist

Use this checklist to track your migration progress.

- [ ] **Update all endpoint URLs** — add `/v2/` prefix to every API path.
- [ ] **Switch authentication** — replace `X-Auth-Token` header with `Authorization: Bearer`.
- [ ] **Handle UUID task IDs** — update database schemas, type checks, and local state from integer to string.
- [ ] **Rename `done` to `completed`** — audit all read and write paths for task objects.
- [ ] **Add `project_id` to task creation** — list available projects and include `project_id` in every `POST /v2/tasks` body.
- [ ] **Unwrap paginated list responses** — replace bare array access with `body["items"]` on all list endpoints.
- [ ] **Update error handling** — account for new 401 (bad auth), 422 (missing `project_id`), and 404 on UUID lookups.
- [ ] **Test end-to-end** — run a full CRUD cycle (create, list, get, update, delete) against v2 before cutting over.

---

## Upgrade Command

Install the latest Zrb CLI:

```bash
pip install --upgrade zrb
```

Verify the installed version:

```bash
zrb --version
# Expected: 2.x.x
```
