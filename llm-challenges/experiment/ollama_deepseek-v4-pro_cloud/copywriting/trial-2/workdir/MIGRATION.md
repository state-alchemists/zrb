# Migrating from Zrb API v1 to v2

**Audience:** Developers actively using the v1 API.
**Goal:** Upgrade your integration from v1 to v2 with minimal disruption.

v2 introduces projects, cursor-based pagination, and stricter authentication. All six breaking changes are covered below with before/after examples.

---

## Breaking Changes

### 1. Endpoint Prefix — `/v2/`

All resource paths are now prefixed with `/v2`. The old paths return HTTP 404.

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

### 2. Authentication Header

The `X-Auth-Token` header is replaced by the standard `Authorization: Bearer` scheme. Requests with the old header receive HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.dev/v2/tasks
```

Regenerate your credentials — v1 API keys are not valid bearer tokens. Obtain a new token from the dashboard.

---

### 3. Task ID — Integer to UUID

Task `id` is now a UUID string instead of an auto-incrementing integer. Any code that assumes a numeric ID or uses integer arithmetic on it will break.

**Before (v1):**

```json
{"id": 42, "title": "Write tests", "done": false}
```

**After (v2):**

```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false}
```

**What to update:**

- All `GET /tasks/{id}`, `PUT /tasks/{id}`, and `DELETE /tasks/{id}` call sites must now pass a UUID string.
- Remove any integer-based logic (e.g., auto-increment assumptions, `id > lastId` comparisons).
- If you previously stored `id` as a database integer column, migrate it to `VARCHAR(36)` or `UUID`.

---

### 4. Field Rename — `done` → `completed`

The boolean field `done` has been renamed to `completed`. Both create and update payloads use the new name. The old field is silently dropped.

**Before (v1):**

```json
// Request:  POST /tasks
{"title": "Write tests"}

// Response: 201 Created
{"id": 42, "title": "Write tests", "done": false, "created_at": "2024-01-15T10:30:00Z"}
```

**After (v2):**

```json
// Request:  POST /v2/tasks
{"title": "Write tests", "project_id": "proj_abc123"}

// Response: 201 Created
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false, "project_id": "proj_abc123", "created_at": "2024-01-15T10:30:00Z"}
```

**Before — updating a task (v1):**

```json
PUT /tasks/42
{"done": true}
```

**After — updating a task (v2):**

```json
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
{"completed": true}
```

Search your codebase for `["']done["']` and replace with `completed` in all request payloads and response parsers.

---

### 5. Project ID Required on Create

`POST /v2/tasks` now requires a `project_id` field. Omitting it returns HTTP 422 with a validation error. There is no default.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"title": "My task"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{"title": "My task", "project_id": "proj_abc123"}'
```

Obtain a `project_id` from the `GET /v2/projects` endpoint or the dashboard. If your workflow has no corresponding v1 concept, create a catch-all project (e.g., "General") to use during migration.

---

### 6. Paginated List Envelope

List endpoints no longer return a bare array. They return a paginated envelope containing `items`, `total`, and `next_cursor`. Use cursor-based pagination to fetch additional pages.

**Before (v1):**

```json
// GET /tasks → bare array
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."}
]
```

**After (v2):**

```json
// GET /v2/tasks → paginated envelope
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Before — iterating all tasks (v1):**

```javascript
const tasks = await fetch("/tasks").then(r => r.json());
for (const task of tasks) {
  // ...
}
```

**After — iterating all tasks (v2):**

```javascript
async function* listTasks() {
  let cursor = null;
  do {
    const params = cursor ? `?cursor=${cursor}` : "";
    const page = await fetch(`/v2/tasks${params}`).then(r => r.json());
    yield* page.items;
    cursor = page.next_cursor;
  } while (cursor);
}

for await (const task of listTasks()) {
  // ...
}
```

Key changes:

- Access items via `response.items`, not the root array.
- `next_cursor` is `null` when the last page is reached — stop paginating.
- Use `?cursor=<value>&limit=<n>` to control page size (default: 20).

---

## Migration Checklist

Use this checklist to track your migration step by step.

- [ ] **Update endpoint paths.** Add `/v2/` prefix to all API calls.
- [ ] **Replace auth header.** Switch from `X-Auth-Token` to `Authorization: Bearer`. Generate a new bearer token.
- [ ] **Migrate task IDs.** Change `id` fields from integer to UUID string. Update any stored references (database columns, cache keys, etc.).
- [ ] **Rename `done` to `completed`.** Update all request payloads and response parsers.
- [ ] **Add `project_id` to task creates.** Decide on a project strategy and ensure `POST /v2/tasks` always includes it.
- [ ] **Update list response handling.** Switch from bare-array access to the paginated envelope (`response.items`). Implement cursor-based pagination if needed.
- [ ] **Test in staging.** Run your full integration test suite against the v2 endpoints.
- [ ] **Deploy.** Roll out the updated client and verify production traffic.

---

## Upgrade Command

```bash
pip install --upgrade zrb
```

After upgrading, restart your application and confirm all endpoints resolve against `/v2/`. The v1 endpoints will be decommissioned 90 days after this release.
