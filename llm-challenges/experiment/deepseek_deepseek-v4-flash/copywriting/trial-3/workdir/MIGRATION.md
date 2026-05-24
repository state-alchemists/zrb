# Zrb API v1 → v2 Migration Guide

Upgrading from Zrb v1 to v2 introduces several breaking changes. This guide covers every change, why it was made, and how to update your code.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [URL Prefix: `/v2/`](#2-url-prefix-v2)
3. [Task ID: Integer → UUID](#3-task-id-integer--uuid)
4. [Field: `done` → `completed`](#4-field-done--completed)
5. [Creating Tasks: `project_id` Is Now Required](#5-creating-tasks-project_id-is-now-required)
6. [List Responses: Paginated Envelope](#6-list-responses-paginated-envelope)
7. [Migration Checklist](#migration-checklist)
8. [Upgrade](#upgrade)

---

## 1. Authentication

**Why:** Standardizing on the Bearer token scheme aligns with widely used auth practices and improves compatibility with existing tooling.

**Change:** The `X-Auth-Token` header is removed. All requests must use an `Authorization: Bearer` header. Requests with the old header receive HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

```python
# Python
headers = {"X-Auth-Token": "abc123"}
response = requests.get("https://api.zrb.dev/tasks", headers=headers)
```

**After (v2):**

```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

```python
# Python
headers = {"Authorization": "Bearer abc123"}
response = requests.get("https://api.zrb.dev/v2/tasks", headers=headers)
```

---

## 2. URL Prefix: `/v2/`

**Why:** Version-prefixed URLs let the API evolve without breaking existing clients on future major versions.

**Change:** All endpoints are now prefixed with `/v2/`.

| Endpoint      | v1                    | v2                         |
|---------------|-----------------------|----------------------------|
| List Tasks    | `GET /tasks`          | `GET /v2/tasks`            |
| Get Task      | `GET /tasks/{id}`     | `GET /v2/tasks/{id}`       |
| Create Task   | `POST /tasks`         | `POST /v2/tasks`           |
| Update Task   | `PUT /tasks/{id}`     | `PUT /v2/tasks/{id}`       |
| Delete Task   | `DELETE /tasks/{id}`  | `DELETE /v2/tasks/{id}`    |

**Before (v1):**

```javascript
// JavaScript
const res = await fetch("https://api.zrb.dev/tasks");
```

**After (v2):**

```javascript
// JavaScript
const res = await fetch("https://api.zrb.dev/v2/tasks");
```

---

## 3. Task ID: Integer → UUID

**Why:** UUIDs eliminate collisions in distributed systems, avoid sequential-ID enumeration attacks, and make client-side ID generation possible.

**Change:** The `id` field on every task object is now a UUID string instead of an integer. All endpoints that accept an `{id}` parameter now expect a UUID string.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
// JavaScript — retrieving a task by integer ID
const res = await fetch("https://api.zrb.dev/tasks/42");
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

```javascript
// JavaScript — retrieving a task by UUID
const res = await fetch("https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890");
```

**Migration note:** If your application stored task IDs as integers, you must update your schema to accept UUID strings (e.g., migrate database columns from `INTEGER` to `UUID` / `VARCHAR(36)`).

---

## 4. Field: `done` → `completed`

**Why:** The name `completed` is more descriptive and consistent with industry conventions for task-management APIs.

**Change:** The boolean task field `done` is renamed to `completed`. Both reading and writing tasks now use the new name. The old field is not present in v2 responses and is ignored if sent in a request body.

**Before (v1):**

```json
// Response body
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

```python
# Python — updating a task
payload = {"title": "Write tests", "done": True}
response = requests.put("https://api.zrb.dev/tasks/42", json=payload)
```

**After (v2):**

```json
// Response body
{
  "id": "a1b2c3d4-...",
  "title": "Write tests",
  "completed": false
}
```

```python
# Python — updating a task
payload = {"title": "Write tests", "completed": True}
response = requests.put("https://api.zrb.dev/v2/tasks/a1b2c3d4-...", json=payload)
```

**Migration note:** Search your codebase for all references to the `.done` key on task objects and rename them to `.completed`.

---

## 5. Creating Tasks: `project_id` Is Now Required

**Why:** v2 introduces project-scoped tasks. Every task must belong to a project, enabling better organization and access control.

**Change:** `POST /v2/tasks` requires a `project_id` field. Omitting it returns HTTP 422 Unprocessable Entity.

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

**Migration note:** Ensure you have a valid `project_id` before creating tasks. You can list available projects via `GET /v2/projects` (see the v2 API reference for details).

---

## 6. List Responses: Paginated Envelope

**Why:** Bare arrays are unbounded — they break under large datasets and offer no way to paginate. The envelope gives you pagination cursors and a total count out of the box.

**Change:** `GET /v2/tasks` no longer returns a bare JSON array. It returns an envelope object containing `items`, `total`, and `next_cursor`.

**Before (v1):**

```javascript
// v1 — bare array, no pagination
const res = await fetch("https://api.zrb.dev/tasks");
const tasks = await res.json();
// tasks is an array: [{id: 1, ...}, {id: 2, ...}]
tasks.forEach(t => console.log(t.title));
```

**After (v2):**

```javascript
// v2 — paginated envelope
const res = await fetch("https://api.zrb.dev/v2/tasks?limit=20");
const page = await res.json();
// page is an object: {items: [...], total: 42, next_cursor: "cursor_xyz"}
page.items.forEach(t => console.log(t.title));

// Fetch the next page
if (page.next_cursor) {
  const next = await fetch(
    `https://api.zrb.dev/v2/tasks?cursor=${page.next_cursor}&limit=20`
  );
}
```

**Query parameters:**
| Param    | Type   | Default | Description                            |
|----------|--------|---------|----------------------------------------|
| `cursor` | string | (none)  | Cursor from the previous page's `next_cursor`. |
| `limit`  | int    | 20      | Max items per page.                    |

---

## Migration Checklist

Use this checklist to track progress when upgrading your application.

- [ ] **Authentication:** Replace all `X-Auth-Token` headers with `Authorization: Bearer <token>`.
- [ ] **URL prefix:** Add `/v2/` to every API endpoint URL.
- [ ] **Task ID type:** Update database schemas and client-side types to accept UUID strings (e.g., `VARCHAR(36)`) instead of integers.
- [ ] **`done` → `completed`:** Rename the field everywhere it appears in your code — request payloads, response parsing, and display logic.
- [ ] **`project_id`:** Ensure every task-creation flow provides a `project_id`. Obtain project IDs from `GET /v2/projects`.
- [ ] **List response handling:** Replace bare-array parsing with the paginated envelope (`items`, `total`, `next_cursor`). Add cursor-based pagination where needed.
- [ ] **Test:** Run your full test suite against the v2 endpoint and verify all 7 checklist items pass.

---

## Upgrade

```bash
pip install --upgrade zrb
```

After upgrading, update your API base URL to `https://api.zrb.dev/v2` and regenerate your Bearer token. Run the migration checklist above before deploying to production.

Need help? Open an issue at https://github.com/state-alchemists/zrb/issues.
