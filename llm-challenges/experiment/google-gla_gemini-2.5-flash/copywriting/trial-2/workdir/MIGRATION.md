# Zrb CLI v1 → v2 Migration Guide

v2 introduces project scoping, cursor-based pagination, stricter authentication, and several renamed fields. Every endpoint path, the auth scheme, the task ID type, and the list response format have changed — rollbacks are not supported.

This guide covers every breaking change with before/after examples. Estimated migration time: **30–60 minutes** for a typical integration.

---

## Breaking Changes at a Glance

| # | Change | Impact |
|---|--------|--------|
| 1 | All endpoints prefixed with `/v2/` | Every URL must be updated |
| 2 | Auth header changed from `X-Auth-Token` to `Authorization: Bearer` | All API clients need new auth logic |
| 3 | Task `id` is now a UUID string (was integer) | ID-dependent code, caches, and stores break |
| 4 | Field `done` renamed to `completed` | All reads and writes of task status break |
| 5 | `project_id` required on creation | Creation requests without it return HTTP 422 |
| 6 | List endpoints return a paginated envelope (was bare array) | All list-response parsers break |

---

## 1. Endpoint Paths

All task endpoints are now prefixed with `/v2/`. The old paths return HTTP 404.

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

`{id}` is now a UUID string — see change #3.

---

## 2. Authentication

The `X-Auth-Token` header is replaced by the standard `Authorization: Bearer` scheme. Requests using the old header receive HTTP 401.

**Before (v1):**

```
X-Auth-Token: sk-abc123
```

**After (v2):**

```
Authorization: Bearer sk-abc123
```

Generate a new API token from the dashboard — v1 API keys are not accepted by v2.

---

## 3. Task ID Type

Task identifiers are now UUID v4 strings instead of auto-incrementing integers. This affects every endpoint that references a task by ID and any local state keyed on task IDs.

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

**Action required:**
- Update any type assertions or database columns from `integer` to `string`/`UUID`.
- Clear any local ID caches — v1 IDs have no correlation to v2 IDs.
- If you rely on monotonic IDs for ordering, use `created_at` instead.

---

## 4. `done` → `completed`

The task status field is renamed from `done` to `completed`. The semantics are identical: `false` means incomplete, `true` means complete.

**Before (v1):**

```json
{
  "title": "Ship v1",
  "done": true
}
```

```bash
curl -X PUT /tasks/42 \
  -H "X-Auth-Token: sk-abc123" \
  -d '{"done": true}'
```

**After (v2):**

```json
{
  "title": "Ship v1",
  "completed": true
}
```

```bash
curl -X PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer sk-abc123" \
  -d '{"completed": true}'
```

**Action required:**
- Rename all references to `done` → `completed` in request bodies and response handlers.
- The old field name is silently ignored in v2 — no error, but the value is not persisted.

---

## 5. `project_id` Required on Creation

Every task must belong to a project. The `project_id` field is required when creating a task. Omitting it returns HTTP 422 with a validation error.

**Before (v1):**

```bash
curl -X POST /tasks \
  -H "X-Auth-Token: sk-abc123" \
  -d '{"title": "New task"}'
```

**After (v2):**

```bash
curl -X POST /v2/tasks \
  -H "Authorization: Bearer sk-abc123" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

**Action required:**
- Obtain a valid `project_id` from the Projects API or dashboard.
- Add `project_id` to all task creation code paths.
- Handle HTTP 422 responses gracefully during rollout.

---

## 6. List Response Format (Pagination Envelope)

List endpoints no longer return a bare array. They return a paginated envelope with `items`, `total`, and `next_cursor`. A `cursor` query parameter controls the page. Default page size is 20 items; override with `?limit=` (max 100).

**Before (v1) — bare array:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**After (v2) — paginated envelope:**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false},
    {"id": "c3d4...", "title": "Ship v1", "completed": true}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

```bash
# v1 — no pagination
curl /tasks

# v2 — first page
curl /v2/tasks?limit=20

# v2 — next page
curl /v2/tasks?cursor=cursor_xyz&limit=20
```

**Action required:**
- Update all list-response parsers to unwrap `response.items` instead of reading the root array.
- Add cursor-pagination logic to fetch all tasks beyond the first page.
- Use `response.total` to display counts instead of `response.items.length` — the latter is capped by the page size.
- On the client side, `next_cursor` being `null` means the last page is reached.

---

## Migration Checklist

- [ ] **Update base URL**: Append `/v2` to all API endpoint paths.
- [ ] **Switch auth header**: Replace `X-Auth-Token` with `Authorization: Bearer`.
- [ ] **Generate a new token**: Create a v2 API token from the dashboard.
- [ ] **Rename `done` → `completed`**: Update all request bodies and response parsers.
- [ ] **Update `id` types**: Change from `integer` to `string`/`UUID` in models, DB columns, and caches.
- [ ] **Add `project_id` to task creation**: Obtain a project ID and include it in every `POST /v2/tasks` request.
- [ ] **Rewrite list-response parsers**: Unwrap `response.items`, use `response.total` for counts, implement cursor pagination.
- [ ] **Handle `next_cursor`**: Loop through pages until `next_cursor` is `null`.
- [ ] **Update tests**: Re-seed test data with UUID IDs and project IDs.
- [ ] **Deploy client first**: Migrate all consumers before switching server-side traffic.
- [ ] **Monitor 4xx/5xx rates**: Watch for spikes in 401 (old auth), 404 (old paths), 422 (missing `project_id`).

---

## Upgrade Command

Install the latest CLI and verify the version:

```bash
# Upgrade
npm install -g zrb@latest

# Verify
zrb --version
# → zrb v2.x.x

# Test a simple request
curl -s -H "Authorization: Bearer $(zrb token)" \
  /v2/tasks?limit=1 | jq '.items[0].completed'
```

v2 resets all API tokens — run `zrb token` (or visit the dashboard) to generate a new one after upgrading.
