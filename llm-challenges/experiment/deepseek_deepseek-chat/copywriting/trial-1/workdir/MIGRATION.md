# Zrb Task API: v1 → v2 Migration Guide

Zrb v2 introduces projects, paginated list endpoints, stricter authentication, and several field changes. All existing v1 endpoints and auth mechanisms are **removed** — requests using the old format will receive HTTP 401 or 404.

This guide covers every breaking change with before/after examples. Estimated migration time for a typical codebase: 1–2 hours.

---

## Breaking Changes at a Glance

| # | Change | v1 | v2 |
|---|--------|----|----|
| 1 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 2 | Auth header | `X-Auth-Token` | `Authorization: Bearer` |
| 3 | Task ID type | integer | UUID string |
| 4 | Field rename | `done` | `completed` |
| 5 | Project requirement | not required | `project_id` required on create |
| 6 | List response format | bare array | paginated envelope |

---

## 1. Endpoint Prefix

All endpoints are now prefixed with `/v2/`. The old paths return 404.

**Before (v1):**

```http
GET /tasks
POST /tasks
GET /tasks/42
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**

```http
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Action:** Update all base URLs in your API client config. Add `/v2/` to every task endpoint.

---

## 2. Authentication Header

The `X-Auth-Token` header is no longer accepted. Use the standard `Authorization: Bearer` scheme instead. Requests with the old header receive HTTP 401.

**Before (v1):**

```http
X-Auth-Token: sk-abc123
```

**After (v2):**

```http
Authorization: Bearer sk-abc123
```

**Action:** Replace `X-Auth-Token` with `Authorization: Bearer` in your HTTP client setup. If you manage tokens programmatically, ensure they are passed in the new header.

---

## 3. Task ID Type (Integer → UUID)

Task IDs are now UUID strings. All integer IDs from v1 are invalid in v2 — you must migrate to the new UUID identifiers.

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
- Re-fetch all existing tasks from v2 to obtain their UUIDs — the old integer IDs do not carry over.
- Update any local caches, URL templates, or route builders that reference task IDs to use UUID strings.
- Change database columns or in-memory stores from `int` to `string (UUID)` types.

---

## 4. Field Rename: `done` → `completed`

The task field indicating completion status has been renamed. The old field is absent in v2 responses; sending `done` in a write request is silently ignored.

**Before (v1) — request:**

```http
PUT /tasks/42
Content-Type: application/json

{
  "title": "Updated title",
  "done": true
}
```

**After (v2) — request:**

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/json
Authorization: Bearer sk-abc123

{
  "title": "Updated title",
  "completed": true
}
```

**Action:** Replace all references to `done` with `completed` in read and write code paths. Update serializers, deserializers, type definitions, and UI components that render or send this field.

---

## 5. Required `project_id` on Creation

Every task must now belong to a project. The `project_id` field is required when creating a task — omitting it returns HTTP 422.

**Before (v1):**

```http
POST /tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

**After (v2):**

```http
POST /v2/tasks
Content-Type: application/json
Authorization: Bearer sk-abc123

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Action:**
- Determine the correct `project_id` for each new task. If your v1 data was project-less, create a default project in v2 and use its UUID.
- Update your task creation form or API client to require and send `project_id`.
- Handle HTTP 422 responses gracefully in case a user omits the field.

---

## 6. List Response Format (Paginated Envelope)

The list endpoint no longer returns a bare array. It returns a paginated envelope with `items`, `total`, and `next_cursor`. Iterate using cursor-based pagination.

**Before (v1) — response:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) — response:**

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "e5f6a7b8-...", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": null
}
```

**Fetching the next page (v2):**

```http
GET /v2/tasks?cursor=next_cursor_value&limit=20
Authorization: Bearer sk-abc123
```

**Action:**
- Unwrap the array from `response.items` instead of reading `response` directly.
- Display or use `response.total` for counts (instead of `response.length`).
- Implement cursor-based pagination: pass `response.next_cursor` as the `?cursor=` query param to fetch the next page. Loop until `next_cursor` is `null`.
- Set `?limit=` to control page size (defaults to 20).

---

## Migration Checklist

Use this checklist to track your migration progress.

- [ ] **1. Endpoint prefix** — Update all task endpoint URLs to include `/v2/` prefix.
- [ ] **2. Authentication** — Replace `X-Auth-Token` header with `Authorization: Bearer <token>`. Regenerate tokens if necessary.
- [ ] **3. Task IDs** — Re-fetch existing tasks to obtain UUIDs. Update all code paths that store, display, or reference integer task IDs.
- [ ] **4. Field rename** — Replace all occurrences of the field `done` with `completed` in both request and response handling.
- [ ] **5. Project ID** — Introduce a `project_id` prompt/field in your task creation flow. Decide on a default project strategy for existing data.
- [ ] **6. Pagination** — Update list response handling to read from `response.items`. Implement cursor-based pagination where you iterate past the first page.
- [ ] **7. Stale references** — Search your codebase for any remaining v1 patterns (integer IDs, bare arrays, `done`, `X-Auth-Token`) and update them.

---

## Upgrade Command

```bash
pip install zrb==2.0.0
```

After upgrading, run your test suite and verify against the v2 endpoints before deploying to production.
