# Zrb API v2 Migration Guide

Upgrading from the v1 Task API to v2 introduces several breaking changes. This guide covers every difference, shows before/after code examples, and provides a step-by-step migration plan.

## Table of Contents

- [Breaking Changes Overview](#breaking-changes-overview)
- [1. Endpoint Path Prefix — `/v2/` Added](#1-endpoint-path-prefix--v2-added)
- [2. Authentication Header — `X-Auth-Token` → `Authorization: Bearer`](#2-authentication-header--x-auth-token--authorization-bearer)
- [3. Task ID Type — Integer → UUID String](#3-task-id-type--integer--uuid-string)
- [4. Field Rename — `done` → `completed`](#4-field-rename--done--completed)
- [5. Required Field — `project_id` on Create](#5-required-field--project_id-on-create)
- [6. List Response Format — Bare Array → Paginated Envelope](#6-list-response-format--bare-array--paginated-envelope)
- [Migration Checklist](#migration-checklist)
- [Upgrade](#upgrade)

---

## Breaking Changes Overview

| # | Change | Impact |
|---|--------|--------|
| 1 | All endpoints prefixed with `/v2/` | URL changes |
| 2 | Auth header: `X-Auth-Token` → `Authorization: Bearer` | Every request fails with 401 until updated |
| 3 | Task `id`: integer → UUID string | All stored references to task IDs break |
| 4 | Field `done` renamed to `completed` | Read and write code referencing `done` produces wrong results or errors |
| 5 | `project_id` required on create | Task creation fails with 422 without it |
| 6 | List responses wrap in paginated envelope | Code assuming a bare array breaks immediately |

---

## 1. Endpoint Path Prefix — `/v2/` Added

All resource paths are now prefixed with `/v2/`.

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

**Action:** Update your base URL or path constants. A single `base_url` variable is the cleanest approach.

---

## 2. Authentication Header — `X-Auth-Token` → `Authorization: Bearer`

The auth mechanism changed from a custom header to the standard Bearer token scheme. Requests using the old header are rejected with HTTP 401.

**Before (v1):**

```
X-Auth-Token: <your_api_key>
```

```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

```python
headers = {"X-Auth-Token": api_key}
response = requests.get(url, headers=headers)
```

**After (v2):**

```
Authorization: Bearer <your_api_token>
```

```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

```python
headers = {"Authorization": f"Bearer {api_token}"}
response = requests.get(url, headers=headers)
```

**Action:** Replace `X-Auth-Token` with `Authorization: Bearer<TOKEN>`. If your API key and token are different credentials, obtain the new token from the dashboard before deploying.

---

## 3. Task ID Type — Integer → UUID String

Task identifiers are now UUID strings instead of auto-incrementing integers. Existing integer IDs are **not** carried over — all tasks received new UUIDs during migration.

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
- Update any stored or hardcoded task IDs to their UUID replacements.
- Remove assumptions about monotonic ordering or sequential IDs.
- Add a one-time mapping step if you maintain external references to task IDs (see [Migration Checklist](#migration-checklist)).

---

## 4. Field Rename — `done` → `completed`

The boolean task status field is renamed from `done` to `completed`. This affects both request payloads and response parsing.

**Before (v1):**

```python
# Reading
if task["done"]:
    print("Task is complete")

# Writing
payload = {"done": True}
```

```bash
curl -X PUT https://api.zrb.dev/tasks/42 \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"done": true}'
```

**After (v2):**

```python
# Reading
if task["completed"]:
    print("Task is complete")

# Writing
payload = {"completed": True}
```

```bash
curl -X PUT https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

**Action:** Replace every occurrence of `done` with `completed` in request bodies and response parsers.

---

## 5. Required Field — `project_id` on Create

Creating a task now requires a `project_id` string. Requests that omit it receive HTTP 422.

**Before (v1):**

```json
POST /tasks
{
  "title": "New task title"
}
```

```python
payload = {"title": "New task title"}
response = requests.post(url, json=payload, headers=headers)
```

**After (v2):**

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

```python
payload = {
    "title": "New task title",
    "project_id": "proj_abc123"
}
response = requests.post(url, json=payload, headers=headers)
```

**Action:** Identify the project each task belongs to and include `project_id` in every create request. A typical pattern is to pick the project from the current UI context or a config value — **do not** hardcode a single value unless your app uses exactly one project.

---

## 6. List Response Format — Bare Array → Paginated Envelope

List endpoints no longer return a bare array. The response is now a paginated envelope containing `items`, `total`, and `next_cursor`.

**Before (v1):**

```json
GET /tasks

[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```python
tasks = response.json()          # bare list
for t in tasks:
    print(t["title"])
```

**After (v2):**

```json
GET /v2/tasks

{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "e5f6a7b8-...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": null
}
```

```python
data = response.json()
tasks = data["items"]            # unwrap envelope
total = data["total"]            # total across all pages
cursor = data["next_cursor"]     # None if last page

if cursor:
    next_url = f"/v2/tasks?cursor={cursor}&limit=20"

for t in tasks:
    print(t["title"])
```

**Action:**
- Access `data["items"]` instead of using the response body directly.
- If you paginate, store `next_cursor` and pass it as the `?cursor=` query param.
- Use `limit` to control page size (default 20).

---

## Migration Checklist

Follow these steps in order for a safe migration.

- [ ] **1. Read the v2 spec** — Familiarise yourself with the full API at `v2_spec.md`.
- [ ] **2. Obtain API tokens** — Generate new Bearer tokens from the dashboard. Do not reuse v1 `X-Auth-Token` values.
- [ ] **3. Build the UUID mapping table** — If your system references task IDs externally (database foreign keys, URLs, cached data), run the one-time ID mapping job provided by the platform before any v2 code goes live.
- [ ] **4. Update the base URL** — Append `/v2` to all endpoint paths.
- [ ] **5. Replace auth headers** — Swap `X-Auth-Token` for `Authorization: Bearer <token>` in every HTTP client.
- [ ] **6. Rename `done` → `completed`** — Update all request payloads and response parsers. Also update any search/filter logic that references the field name.
- [ ] **7. Add `project_id` to create requests** — Ensure your task creation flow always sends a valid `project_id`.
- [ ] **8. Rewrite list-response handling** — Read `response.data["items"]` instead of `response.data`. Add pagination logic if you consume more than one page.
- [ ] **9. Audit type assumptions** — Search for places where your code assumes `id` is an integer (e.g., `isinstance(id, int)`, arithmetic, `<`/`>` comparisons).
- [ ] **10. Run integration tests** — Against a staging v2 environment. Cover create, read, update, delete, and list-with-pagination.
- [ ] **11. Deploy to production** — After all tests pass.

---

## Upgrade

Update to the latest Zrb CLI that targets the v2 API:

```bash
pip install --upgrade zrb
```
