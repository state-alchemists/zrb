# Zrb API v1 → v2 Migration Guide

Zrb v2 introduces projects, cursor-based pagination, stricter authentication, and several breaking API changes. This guide walks you through every difference so you can migrate your code with confidence.

---

## Quick Reference

| Area | v1 (Old) | v2 (New) |
|------|----------|----------|
| Endpoint prefix | `/tasks` | `/v2/tasks` |
| Auth header | `X-Auth-Token: <key>` | `Authorization: Bearer <token>` |
| Task `id` type | integer (e.g., `42`) | UUID string (e.g., `"a1b2c3d4-..."`) |
| Task completion field | `done` | `completed` |
| Task creation | title only | title + required `project_id` |
| List response | bare array | paginated envelope `{items, total, next_cursor}` |

---

## Breaking Changes

### 1. Endpoint Prefix

All endpoints are now prefixed with `/v2/`. Requests to the old `/tasks` paths return **404**.

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

### 2. Authentication Header

The custom `X-Auth-Token` header is replaced by the standard Bearer token pattern. Requests with the old header receive **HTTP 401**.

**Before (v1):**

```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.dev/v2/tasks
```

### 3. Task `id` Is Now a UUID String

Task identifiers changed from auto-incrementing integers to UUID v4 strings. Update your data layer, URL construction, and any local ID lookups.

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
// v1 client code
async function getTask(id) {
  const res = await fetch(`https://api.zrb.dev/tasks/${id}`);
  return res.json();
}
getTask(42);
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
// v2 client code
async function getTask(id) {
  const res = await fetch(`https://api.zrb.dev/v2/tasks/${id}`);
  return res.json();
}
getTask("a1b2c3d4-e5f6-7890-abcd-ef1234567890");
```

### 4. `done` Renamed to `completed`

The field that tracks task completion has been renamed. Requests using the old field name are **silently ignored** — the task retains its current completion state.

**Before (v1):**

```json
// POST /tasks — request body
{ "title": "Buy milk" }

// PUT /tasks/42 — request body
{ "title": "Buy milk", "done": true }
```

```javascript
// v1 client code
if (task.done) {
  console.log("Task is complete");
}
```

**After (v2):**

```json
// POST /v2/tasks — request body
{ "title": "Buy milk", "project_id": "proj_abc123" }

// PUT /v2/tasks/{id} — request body
{ "title": "Buy milk", "completed": true }
```

```javascript
// v2 client code
if (task.completed) {
  console.log("Task is complete");
}
```

### 5. `project_id` Is Now Required on Task Creation

Every task must belong to a project. The `project_id` field is required when creating a task. Omitting it returns **HTTP 422** with a validation error.

You will need to create a project (or use an existing one) before creating tasks.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "project_id": "proj_abc123"}'
```

### 6. List Endpoints Return a Paginated Envelope

Instead of a bare array, all list endpoints now return a paginated envelope with `items`, `total`, and `next_cursor`. Use the cursor to fetch subsequent pages.

**Before (v1):**

```json
// GET /tasks
[
  { "id": 1, "title": "Buy milk", "done": false, "created_at": "..." },
  { "id": 2, "title": "Ship v1", "done": true, "created_at": "..." }
]
```

```javascript
// v1 — directly iterate the array
const tasks = await res.json();
tasks.forEach(task => process(task));
```

**After (v2):**

```json
// GET /v2/tasks?limit=20
{
  "items": [
    { "id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..." }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// v2 — unwrap the envelope, then paginate
async function fetchAllTasks(baseUrl) {
  let cursor = null;
  const all = [];
  do {
    const params = new URLSearchParams({ limit: 20 });
    if (cursor) params.set("cursor", cursor);
    const res = await fetch(`${baseUrl}?${params}`);
    const page = await res.json();
    all.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return all;
}
```

---

## Migration Checklist

Follow these steps in order:

- [ ] **Regenerate API tokens** — Replace your `X-Auth-Token` keys with Bearer tokens from the Zrb dashboard.
- [ ] **Update base URL** — Change all API paths from `/tasks` to `/v2/tasks`.
- [ ] **Update auth headers** — Replace `X-Auth-Token: <key>` with `Authorization: Bearer <token>` in every request.
- [ ] **Handle UUID IDs** — Update your data layer, database schema, and URL builders to accept and store UUID strings instead of integers.
- [ ] **Rename `done` to `completed`** — Update all read and write paths that reference the task completion field.
- [ ] **Add `project_id` to task creation** — Ensure every `POST /v2/tasks` call includes a valid `project_id`. Create a project first if needed.
- [ ] **Unwrap list responses** — Change array iteration to read from `.items`, and add cursor-based pagination logic for large result sets.
- [ ] **Run integration tests** — Exercise every CRUD path against a staging v2 endpoint to catch regressions.

---

## Upgrade

Once your code is migrated, install the latest Zrb CLI:

```bash
pip install --upgrade zrb
```

Verify the upgrade:

```bash
zrb --version
# → zrb 2.x.x
```
