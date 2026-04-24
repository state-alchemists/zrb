# Zrb CLI v1 → v2 Migration Guide

This guide covers every breaking change between Zrb API v1 and v2. Upgrading is
not backward-compatible — please read each section and update your code accordingly.

## Table of Contents

1. [Breaking Change Overview](#breaking-change-overview)
2. [Authentication](#1-authentication-header-renamed)
3. [Base URL & Endpoint Paths](#2-base-url--endpoint-paths)
4. [Task ID Type: Integer → UUID](#3-task-id-integer--uuid-string)
5. [Task Field: `done` → `completed`](#4-task-field-done--completed)
6. [Creating Tasks Now Requires `project_id`](#5-creating-tasks-now-requires-project_id)
7. [List Responses Are Now Paginated](#6-list-responses-are-now-enveloped--paginated)
8. [Migration Checklist](#migration-checklist)
9. [Upgrade Command](#upgrade-command)

---

## Breaking Change Overview

| # | Area | v1 | v2 |
|---|------|----|----|
| 1 | Authentication header | `X-Auth-Token` | `Authorization: Bearer` |
| 2 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 3 | Task `id` type | integer | UUID string |
| 4 | Task completion field | `done` | `completed` |
| 5 | Create task payload | `title` only | `title` + `project_id` (required) |
| 6 | List response format | bare array | paginated envelope |

---

## 1. Authentication Header Renamed

The `X-Auth-Token` header is **removed**. Use the standard Bearer token scheme instead.
Requests with the old header receive `HTTP 401`.

**Before (v1):**

```http
X-Auth-Token: abc123
```

**After (v2):**

```http
Authorization: Bearer <your_api_token>
```

---

## 2. Base URL / Endpoint Paths

All endpoint paths now carry a `/v2/` prefix. Requests to `/tasks` will **not** be
forwarded.

| Operation | v1 | v2 |
|-----------|----|----|
| List tasks | `GET /tasks` | `GET /v2/tasks` |
| Get task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create task | `POST /tasks` | `POST /v2/tasks` |
| Update task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**Before (v1):**

```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer <token>" https://api.zrb.dev/v2/tasks
```

---

## 3. Task ID: Integer → UUID String

Task IDs are now UUID v4 strings instead of auto-incrementing integers. Code that
assumes a numeric type, stores IDs in integer columns, or constructs URLs with
integer IDs will break.

**Before (v1):**

```json
{ "id": 42, "title": "Write tests", "done": false }
```

**After (v2):**

```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false }
```

**Impact:**

- Database columns storing task IDs must change from `INTEGER` to `UUID` / `CHAR(36)`.
- Hard-coded test IDs and fixtures must be updated.
- Routes or clients that validate `typeof id === "number"` will need updating.

---

## 4. Task Field: `done` → `completed`

The boolean field `done` has been renamed to `completed`. Both API payloads and
server responses use the new name.

**Before (v1) — creating a task:**

```bash
curl -X POST /tasks \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "done": false}'
```

**After (v2):**

```bash
curl -X POST /v2/tasks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "completed": false, "project_id": "proj_abc123"}'
```

**Before (v1) — updating a task:**

```json
{ "title": "Updated title", "done": true }
```

**After (v2):**

```json
{ "title": "Updated title", "completed": true }
```

Search your codebase for `done` references in task-related code and rename to `completed`.

---

## 5. Creating Tasks Now Requires `project_id`

v1 allowed creating a task with just a `title`. v2 makes `project_id` a **required**
field. Omitting it returns `HTTP 422 Unprocessable Entity`.

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

**Action required:**

1. Obtain a valid `project_id` (contact your admin or use the projects API).
2. Update every task creation call to include `project_id`.
3. If user-facing, update your forms/UI to collect a project selection.

---

## 6. List Responses Are Now Enveloped & Paginated

v1 returned a bare JSON array. v2 wraps the items in a paginated envelope.

**Before (v1) — list response:**

```json
[
  { "id": 1, "title": "Buy milk", "done": false, "created_at": "..." },
  { "id": 2, "title": "Ship v1", "done": true, "created_at": "..." }
]
```

**After (v2) — list response:**

```json
{
  "items": [
    { "id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..." },
    { "id": "c3d4...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..." }
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

**What to update:**

- Access list results via `response.items` instead of indexing the response directly.
- Use `response.next_cursor` (pass as `?cursor=<value>`) to fetch subsequent pages.
- The default page size is 20 items. Override with `?limit=100`.

**Before (v1) — iterating results:**

```javascript
const tasks = await fetch("/tasks").then(r => r.json());
tasks.forEach(t => console.log(t.title));
```

**After (v2):**

```javascript
const { items, total, next_cursor } = await fetch("/v2/tasks").then(r => r.json());
items.forEach(t => console.log(t.title));
```

---

## Migration Checklist

Use this checklist to track your migration progress.

- [ ] **Update authentication**: replace `X-Auth-Token` with `Authorization: Bearer` in all requests.
- [ ] **Prefix endpoints**: change `/tasks` → `/v2/tasks` everywhere.
- [ ] **Change ID types**: update database schemas, models, and validation to handle UUID strings instead of integers.
- [ ] **Rename `done` → `completed`**: update request payloads, response handlers, and local data models.
- [ ] **Add `project_id`**: include it in every task creation call. Update forms and UIs.
- [ ] **Handle paginated list responses**: replace bare-array access with `response.items`, use `next_cursor` for pagination.
- [ ] **Update tests and fixtures**: refresh hard-coded IDs, mock responses, and test assertions.
- [ ] **Update documentation**: internal API docs, READMEs, and onboarding materials.

---

## Upgrade Command

To upgrade the Zrb CLI to v2:

```bash
zrb upgrade
```

Verify the installed version:

```bash
zrb --version
```
