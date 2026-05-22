# Zrb CLI v1 → v2 Migration Guide

Zrb v2 introduces projects, paginated list responses, and stricter authentication. The API surface has six breaking changes. This guide covers each one with before/after examples so you can upgrade with confidence.

- [Breaking Change 1: Endpoint URL Prefix](#breaking-change-1-endpoint-url-prefix)
- [Breaking Change 2: Authentication Header](#breaking-change-2-authentication-header)
- [Breaking Change 3: Task ID Type (Integer → UUID)](#breaking-change-3-task-id-type-integer--uuid)
- [Breaking Change 4: Field Rename (`done` → `completed`)](#breaking-change-4-field-rename-done--completed)
- [Breaking Change 5: Required `project_id` on Create](#breaking-change-5-required-project_id-on-create)
- [Breaking Change 6: List Response Format (Bare Array → Paginated Envelope)](#breaking-change-6-list-response-format-bare-array--paginated-envelope)
- [Migration Checklist](#migration-checklist)
- [Upgrade Command](#upgrade-command)

---

## Breaking Change 1: Endpoint URL Prefix

All endpoints move from `/tasks` to `/v2/tasks`.

| Method | v1 | v2 |
|--------|----|----|
| List Tasks | `GET /tasks` | `GET /v2/tasks` |
| Get Task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create Task | `POST /tasks` | `POST /v2/tasks` |
| Update Task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete Task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks
```

---

## Breaking Change 2: Authentication Header

The authentication header has changed from `X-Auth-Token` to the standard `Authorization: Bearer` scheme. Requests using the old header will receive HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

Update all SDK clients, scripts, and hardcoded headers.

---

## Breaking Change 3: Task ID Type (Integer → UUID)

Task IDs are now UUID strings instead of auto-incrementing integers. All endpoints that accept an `{id}` path parameter now expect a UUID.

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks/42
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Existing integer IDs are **not** preserved. You must re-fetch tasks to discover their v2 UUIDs.

---

## Breaking Change 4: Field Rename (`done` → `completed`)

The `done` boolean field has been renamed to `completed`. This affects both request payloads and response objects.

**Before (v1) — response:**

```json
{
  "id": 42,
  "title": "Ship v1",
  "done": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2) — response:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v1",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Before (v1) — update request:**

```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2) — update request:**

```json
{
  "title": "Updated title",
  "completed": true
}
```

Search your codebase for references to `response.done`, `task["done"]`, and any update payloads containing the `done` key.

---

## Breaking Change 5: Required `project_id` on Create

Task creation now requires a `project_id` field. Omitting it returns HTTP 422.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write tests"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write tests", "project_id": "proj_abc123"}'
```

Obtain a valid `project_id` by listing projects (or from your project settings dashboard).

---

## Breaking Change 6: List Response Format (Bare Array → Paginated Envelope)

List endpoints no longer return a bare array. They return a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**

```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Buy milk",
      "completed": false,
      "project_id": "proj_abc123",
      "created_at": "..."
    }
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

**Client-side changes required:**

```javascript
// v1 — bare array
const tasks = await response.json();
tasks.forEach(t => console.log(t.title));

// v2 — paginated envelope
const body = await response.json();
body.items.forEach(t => console.log(t.title));
```

To fetch the next page, pass the cursor:

```bash
curl "https://api.zrb.dev/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer abc123"
```

The default page size is 20. Use the `limit` query parameter (max 100) to control it.

---

## Migration Checklist

Use this checklist to track your migration. Each item links to its detailed section above.

- [ ] **1. Update endpoint URLs** — Replace all `/tasks` paths with `/v2/tasks`. ([details](#breaking-change-1-endpoint-url-prefix))
- [ ] **2. Update authentication headers** — Replace `X-Auth-Token` with `Authorization: Bearer`. ([details](#breaking-change-2-authentication-header))
- [ ] **3. Migrate task ID handling** — Expect UUID strings instead of integers. Re-fetch existing tasks to discover their v2 IDs. ([details](#breaking-change-3-task-id-type-integer--uuid))
- [ ] **4. Rename `done` to `completed`** — Update all request payloads and response parsing to use the new field name. ([details](#breaking-change-4-field-rename-done--completed))
- [ ] **5. Add `project_id` to create requests** — Include a valid `project_id` in every `POST /v2/tasks` body. ([details](#breaking-change-5-required-project_id-on-create))
- [ ] **6. Adapt list response parsing** — Unwrap the paginated envelope: access `items`, `total`, `next_cursor`. Add cursor-based pagination logic if you fetch more than 20 items. ([details](#breaking-change-6-list-response-format-bare-array--paginated-envelope))
- [ ] **7. Test end-to-end** — Run your integration tests against the v2 API. Verify CRUD operations, pagination, and error handling (401 for bad auth, 422 for missing `project_id`).

---

## Upgrade Command

```bash
pip install --upgrade zrb
```

After upgrading, regenerate any client SDK or type bindings to match the v2 schemas above. Run the checklist before deploying to production.
