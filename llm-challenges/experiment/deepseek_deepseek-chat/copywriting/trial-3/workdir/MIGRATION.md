# Zrb API v1 → v2 Migration Guide

**Audience:** Developers actively using the v1 API.
**Goal:** Upgrade your integration to v2 with minimal downtime and no unexpected breakage.

v2 introduces projects, pagination, and stricter authentication. Every v1 endpoint continues to exist but will be deprecated after the v2 grace period. This guide covers every breaking change so you can migrate with confidence.

---

## Breaking Changes at a Glance

| # | Area | v1 | v2 |
|---|------|----|----|
| 1 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 2 | Authentication | `X-Auth-Token` header | `Authorization: Bearer` header |
| 3 | Task `id` type | integer | UUID string |
| 4 | Field `done` → `completed` | `"done": true` | `"completed": true` |
| 5 | Create Task requirement | `title` only | `title` + `project_id` (required) |
| 6 | List response format | bare array | paginated envelope |

---

## 1. Endpoint Prefix

All resource paths are now prefixed with `/v2/`.

**Before (v1):**

```
GET /tasks
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**

```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Update your base URL or route templates to include `/v2/`.

---

## 2. Authentication Header

The custom `X-Auth-Token` header has been replaced with the standard `Authorization: Bearer` scheme. Requests using the old header receive a `401 Unauthorized`.

**Before (v1):**

```
X-Auth-Token: <your_api_key>
```

**After (v2):**

```
Authorization: Bearer <your_api_token>
```

Replace the header name and value in your HTTP client configuration. If you previously stored `X-Auth-Token`, you will need a v2 token — re-issue credentials from the admin panel.

---

## 3. Task ID Type: Integer → UUID

Task `id` is now a UUID string instead of an auto-incrementing integer. This affects all endpoints that reference a task by ID (`GET`, `PUT`, `DELETE`), and all code that stores or compares task IDs.

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
// v1: id is an integer
const taskId = task.id;          // 42
const url = `/tasks/${taskId}`;  // /tasks/42
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
// v2: id is a UUID string
const taskId = task.id;          // "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
const url = `/v2/tasks/${taskId}`;
```

**Migration notes:**
- Do not cast or parse the new IDs — treat them as opaque strings.
- Existing integer IDs are **not preserved** in v2. Map old IDs to new UUIDs via the response on first v2 request, or use the migration endpoint (if available in your deployment).
- Update database schemas and any `Number`-based type annotations to `string`.

---

## 4. Field Rename: `done` → `completed`

The task boolean field `done` has been renamed to `completed`. The semantics are identical — `false` means not finished, `true` means finished.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

```javascript
// v1
console.log(task.done);
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

```javascript
// v2
console.log(task.completed);
```

This affects **both** reads and writes:

**Create/Update request (v1 — broken in v2):**

```json
{
  "title": "Updated title",
  "done": true
}
```

**Create/Update request (v2 — correct):**

```json
{
  "title": "Updated title",
  "completed": true
}
```

---

## 5. Create Task Requires `project_id`

Creating a task in v2 requires a `project_id` string. Omitting it returns `422 Unprocessable Entity`. There is no fallback or default project.

**Before (v1):**

```bash
curl -X POST /tasks \
  -H "X-Auth-Token: <key>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

**After (v2):**

```bash
curl -X POST /v2/tasks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

**Migration steps:**
1. Determine which project each new task should belong to.
2. If you have a flat task list in v1, create a default project in v2 and use its `project_id` for all migrated tasks.
3. Add `project_id` validation at the point of task creation in your application.

---

## 6. List Response Format: Bare Array → Paginated Envelope

`GET /tasks` no longer returns a bare array. All list endpoints return a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1) — `GET /tasks`:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
// v1: response is the array
const tasks = response;        // [{id: 1, ...}, {id: 2, ...}]
console.log(tasks.length);
```

**After (v2) — `GET /v2/tasks`:**

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "e5f67890-...", "title": "Ship v1", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// v2: response is the envelope
const tasks = response.items;  // [{id: "a1b2c3d4-...", ...}, {id: "e5f67890-...", ...}]
const total = response.total;  // 42

// Paginate
if (response.next_cursor) {
  const nextPage = await fetch(`/v2/tasks?cursor=${response.next_cursor}`);
}
```

**Migration notes:**
- Always access the list through `response.items`, not the response root.
- Use `response.total` for total count (previously `response.length`).
- Use `response.next_cursor` for pagination. Pass it as `?cursor=<value>` on subsequent requests. Use `limit` to control page size (default: 20).

---

## Migration Checklist

Follow these steps in order. Test each before proceeding to the next.

- [ ] **Issue v2 credentials.** Generate v2 bearer tokens for each integration. The old `X-Auth-Token` values will not work.
- [ ] **Update authentication.** Replace `X-Auth-Token` header with `Authorization: Bearer <v2_token>` in all clients.
- [ ] **Update endpoint prefix.** Prepend `/v2/` to every API path.
- [ ] **Update `done` → `completed`.** Rename the field in all read and write code paths. Update types, schemas, and serialization logic.
- [ ] **Update ID handling.** Change `id` from integer to string. Remove any integer arithmetic on task IDs. Update database column types and ORM models.
- [ ] **Add `project_id` to task creation.** Identify or create a project, and pass its ID with every `POST /v2/tasks` call.
- [ ] **Update list response parsing.** Access `response.items` instead of the response root. Use `response.total` for counts. Implement cursor-based pagination if you fetch more than 20 items.
- [ ] **Test every endpoint.** Run your full integration test suite against v2. Pay special attention to pagination, UUID handling, and the new `completed` field.
- [ ] **Monitor for v1 deprecation warnings.** After validating v2, plan to retire v1 call sites.

---

## Upgrade Command

If you are using the `zrb` CLI tool:

```bash
zrb upgrade --to v2
```

This updates your local configuration, migrates stored credentials to the bearer token format, and sets the default API path prefix to `/v2/`. Run `zrb help` after upgrading to verify the new defaults.

For manual upgrades, update your environment variables:

```bash
# Before (v1)
export ZRB_API_KEY="your_api_key"
export ZRB_BASE_URL="https://api.zrb.dev"

# After (v2)
export ZRB_TOKEN="your_bearer_token"
export ZRB_BASE_URL="https://api.zrb.dev/v2"
```
