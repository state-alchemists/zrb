# Zrb CLI v2 — Migration Guide

This guide covers every breaking change between Zrb Task API v1 and v2. Each section describes the change, shows the old and new patterns, and explains what you need to update.

---

## Table of Contents

1. [Endpoint Prefix: `/v2/`](#1-endpoint-prefix-v2)
2. [Authentication: From `X-Auth-Token` to Bearer Token](#2-authentication-from-x-auth-token-to-bearer-token)
3. [Task ID: Integer to UUID](#3-task-id-integer-to-uuid)
4. [Field Rename: `done` → `completed`](#4-field-rename-done--completed)
5. [Project Requirement: `project_id` Is Now Mandatory](#5-project-requirement-project_id-is-now-mandatory)
6. [List Responses: Bare Array to Paginated Envelope](#6-list-responses-bare-array-to-paginated-envelope)
7. [Migration Checklist](#7-migration-checklist)
8. [Upgrade Command](#8-upgrade-command)

---

## 1. Endpoint Prefix: `/v2/`

All endpoints are now mounted under `/v2/`. Calls to the bare `/tasks` path will fail.

**Before (v1):**

```
POST /tasks
GET /tasks
GET /tasks/{id}
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**

```
POST /v2/tasks
GET /v2/tasks
GET /v2/tasks/{id}
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

**Action:** Update all base URLs in your API client configuration. If you use an environment variable, change `ZRB_API_URL=https://api.zrb.dev` to `ZRB_API_URL=https://api.zrb.dev/v2` (or equivalent).

---

## 2. Authentication: From `X-Auth-Token` to Bearer Token

The authentication mechanism has changed from a custom header to the standard Bearer token scheme. v1 credentials will receive a `401` response.

**Before (v1):**

```
X-Auth-Token: sk-abc123
```

**After (v2):**

```
Authorization: Bearer sk-abc123
```

**Action:** Replace your custom header with the standard `Authorization` header. Your existing token value carries over — only the header name and format change.

---

## 3. Task ID: Integer to UUID

Task IDs are now UUID strings instead of auto-incrementing integers. This affects all endpoints that accept or return task IDs.

**Before (v1) — integer IDs:**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2) — UUID string IDs:**

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

- **On read:** Update any code that assumes `id` is a number — comparison operators (`>`, `<`), modulo arithmetic, or integer formatting will break. Treat `id` as an opaque string.
- **On write:** When calling `GET /v2/tasks/{id}`, `PUT /v2/tasks/{id}`, or `DELETE /v2/tasks/{id}`, pass the UUID string directly. The v1 integer IDs are **not** forward-compatible — you must re-fetch or re-create tasks under v2 to obtain their new UUIDs.
- **Local caches:** If you store task IDs locally, re-seed your cache from v2 responses.

---

## 4. Field Rename: `done` → `completed`

The boolean field indicating task completion has been renamed from `done` to `completed`.

**Before (v1):**

```json
{
  "title": "Write tests",
  "done": false
}
```

```bash
# Reading the field
task.done

# Updating
curl -X PUT /tasks/42 \
  -H "X-Auth-Token: sk-abc123" \
  -d '{"done": true}'
```

**After (v2):**

```json
{
  "title": "Write tests",
  "completed": false
}
```

```bash
# Reading the field
task.completed

# Updating
curl -X PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer sk-abc123" \
  -d '{"completed": true}'
```

**Action:** Rename all references from `.done` / `["done"]` to `.completed` / `["completed"]` in your application code, database mappings, and serialization layers. Update any UI labels that display "Done" to "Completed" for consistency.

---

## 5. Project Requirement: `project_id` Is Now Mandatory

Every task must now belong to a project. The `project_id` field is **required** when creating a task. Omitting it returns `422 Unprocessable Entity`.

**Before (v1) — creating a task without a project:**

```bash
curl -X POST /tasks \
  -H "X-Auth-Token: sk-abc123" \
  -d '{"title": "Fix login bug"}'
```

**After (v2) — `project_id` is required:**

```bash
curl -X POST /v2/tasks \
  -H "Authorization: Bearer sk-abc123" \
  -d '{"title": "Fix login bug", "project_id": "proj_abc123"}'
```

**Action:**

1. Choose a project strategy — use a default project for legacy tasks, a per-team mapping, or let users select a project at creation time.
2. Obtain valid `project_id` values from the new `/v2/projects` endpoint (if available) or your project management admin.
3. Update all task-creation paths (CLI flags, UI forms, scripts, tests) to include `project_id`.

---

## 6. List Responses: Bare Array to Paginated Envelope

All list endpoints now return a paginated envelope instead of a bare JSON array. This avoids unbounded response sizes and enables cursor-based pagination.

**Before (v1) — bare array:**

```
GET /tasks

→
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) — paginated envelope:**

```
GET /v2/tasks?limit=20

→
{
  "items": [ ... ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Access the task list via `response.items`, not the response itself. For pagination:

| Step | Code |
|------|------|
| Fetch first page | `GET /v2/tasks?limit=20` |
| Fetch next page  | `GET /v2/tasks?cursor=cursor_xyz` |
| End of list      | `next_cursor` is `null` |

Note: `v1` clients that iterate over the response as if it were an array will silently break. You must now dereference `items`.

**Action:** Update deserialization logic to unwrap `response.items`. Add cursor-tracking state if you need to paginate beyond the first page.

---

## 7. Migration Checklist

Use this checklist to track your migration progress. Tick items as you complete them.

- [ ] **Update base URLs.** Prefix all API paths with `/v2/`.
- [ ] **Switch authentication headers.** Replace `X-Auth-Token` with `Authorization: Bearer <token>`.
- [ ] **Handle UUID IDs.** Update ID storage, comparison, and display to use UUID strings.
- [ ] **Rename `done` to `completed`.** Update all reads and writes of the completion field.
- [ ] **Provide `project_id`.** Decide on a project strategy and add `project_id` to every task creation call. Handle `422` errors gracefully for a transition period.
- [ ] **Unwrap list responses.** Change list-response handling from direct array access to `response.items`. Add pagination cursor logic if needed.
- [ ] **Update tests.** Every test fixture, assertion, and mock that touches tasks needs updating.
- [ ] **Update documentation.** Refresh internal docs, README examples, and developer onboarding materials to use v2 patterns.
- [ ] **Audit stored data.** If you persist task IDs (databases, config files, session storage), plan a data migration or a re-fetch from v2.

---

## 8. Upgrade Command

Update to the latest v2 release:

```bash
npm install -g @zrb/cli@latest
```

Verify the installed version:

```bash
zrb --version
# Expected: 2.x.x
```

Run the built-in upgrade helper to check your configuration for v2 compatibility:

```bash
zrb migrate check
```

This will scan your config files, environment variables, and stored credentials, flagging anything that needs attention.
