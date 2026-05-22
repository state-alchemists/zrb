# Zrb CLI v1 → v2 Migration Guide

Zrb v2 introduces project scoping, cursor-based pagination, and stricter
authentication. All v1 endpoints still run under the `/v1/` namespace during
the deprecation window, but new features ship exclusively on v2.

This guide covers every breaking change.

- [Breaking Changes](#breaking-changes)
  - [1. URL Prefix: `/tasks` → `/v2/tasks`](#1-url-prefix-tasks--v2tasks)
  - [2. Authentication: `X-Auth-Token` → Bearer Token](#2-authentication-x-auth-token--bearer-token)
  - [3. Task ID: Integer → UUID](#3-task-id-integer--uuid)
  - [4. Field Rename: `done` → `completed`](#4-field-rename-done--completed)
  - [5. Create Task Requires `project_id`](#5-create-task-requires-project_id)
  - [6. List Response: Bare Array → Paginated Envelope](#6-list-response-bare-array--paginated-envelope)
- [Migration Checklist](#migration-checklist)
- [Upgrade](#upgrade)

---

## Breaking Changes

### 1. URL Prefix: `/tasks` → `/v2/tasks`

All endpoints are now prefixed with `/v2/`. The old paths return `404`.

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks
curl https://api.zrb.dev/tasks/42
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks
curl https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication: `X-Auth-Token` → Bearer Token

The `X-Auth-Token` header is no longer accepted. Use the standard
`Authorization: Bearer` header instead. Requests with the old header
receive HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.dev/v2/tasks
```

Regenerate your API token from the dashboard — v1 keys are separate from
v2 bearer tokens.

---

### 3. Task ID: Integer → UUID

Task identifiers are now UUID v4 strings. All integer IDs from v1 are
reassigned on import into v2. Look up migrated IDs via the `/v2/tasks`
endpoint.

**Before (v1) — integer ID:**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2) — UUID string:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Replace any code that assumes `id` is an integer — switch from numeric
parsing to string handling in your client.

---

### 4. Field Rename: `done` → `completed`

The boolean field indicating task completion is renamed from `done` to
`completed`. The old field is absent from v2 responses and ignored on
write.

**Before (v1):**

```javascript
// POST /tasks
{ "title": "Ship v2", "done": false }

// reading a response
if (task.done) { /* ... */ }
```

**After (v2):**

```javascript
// POST /v2/tasks
{ "title": "Ship v2", "completed": false, "project_id": "proj_abc123" }

// reading a response
if (task.completed) { /* ... */ }
```

---

### 5. Create Task Requires `project_id`

`POST /v2/tasks` now requires a `project_id` field. Omitting it returns
HTTP 422. There is no default project — you must create or identify one
first.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_api_token" \
  -d '{"title": "Buy milk", "project_id": "proj_abc123"}'
```

List available projects via `GET /v2/projects`.

---

### 6. List Response: Bare Array → Paginated Envelope

All list endpoints now return a paginated envelope instead of a raw JSON
array. The default page size is 20 items.

**Before (v1) — bare array:**

```json
[
  { "id": 1, "title": "Buy milk", "done": false, "created_at": "..." },
  { "id": 2, "title": "Ship v1", "done": true, "created_at": "..." }
]
```

**After (v2) — paginated envelope:**

```json
{
  "items": [
    { "id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..." }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Traverse pages by passing `?cursor=<next_cursor>`:

```bash
curl "https://api.zrb.dev/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer your_api_token"
```

Update client code to unwrap `response.items` instead of consuming the
response body directly as an array.

---

## Migration Checklist

- [ ] **Regenerate API tokens** — obtain a v2 bearer token from the
      dashboard. v1 `X-Auth-Token` values will not work.
- [ ] **Update all base URLs** — prepend `/v2` to every endpoint path.
- [ ] **Replace the auth header** — change `X-Auth-Token` to
      `Authorization: Bearer` in every request.
- [ ] **Migrate task IDs to strings** — ensure IDs are stored and handled
      as UUID strings, not integers.
- [ ] **Rename `done` → `completed`** — update all request payloads and
      response parsers.
- [ ] **Add `project_id` to task creation** — choose a project for new
      tasks or create one via `POST /v2/projects`.
- [ ] **Handle paginated list responses** — unwrap `response.items` and
      implement cursor-based pagination for full result sets.
- [ ] **Update client models/schemas** — refresh your typed interfaces,
      type stubs, or OpenAPI-generated clients to match the v2 shapes.
- [ ] **Run integration tests** — verify the full workflow against a
      staging account before cutting over.
- [ ] **Verify UUID lookups** — ensure `GET /v2/tasks/{id}` is called
      with UUIDs, not stale integer IDs.

---

## Upgrade

Install the latest Zrb CLI and upgrade your project dependencies:

```bash
pip install --upgrade zrb
```

Verify the installed version:

```bash
zrb --version
# Expected: 2.x.x
```
