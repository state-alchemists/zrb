# Zrb API v1 → v2 Migration Guide

v2 overhauls auth, resource identification, and task semantics. Every v1 endpoint, auth mechanism, and response format is affected. Read each section below — your v1 client **will not work** against v2 without changes.

---

## At a Glance: Breaking Changes

| # | Change | Impact |
|---|--------|--------|
| 1 | All endpoints move to `/v2/` | Update every base URL |
| 2 | Auth header: `X-Auth-Token` → `Authorization: Bearer` | All requests rejected with 401 |
| 3 | Task `id`: integer → UUID string | Store/cache keys, URL building, type checks |
| 4 | Task field `done` → `completed` | All read/write paths referencing `done` |
| 5 | Create Task requires `project_id` | New field, 422 if omitted |
| 6 | List responses: bare array → paginated envelope | Client parsing breaks |

---

## 1. Endpoint Paths — `/v2/` Prefix

Every resource route is now prefixed with `/v2/`.

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

**Action:** Update all base URL or route templates to include `/v2/`.

---

## 2. Authentication — Bearer Token

`X-Auth-Token` is removed. Requests using it receive HTTP 401. Use an `Authorization: Bearer` header instead.

**Before (v1):**

```bash
curl -H "X-Auth-Token: sk_abc123" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer zrb2_abc123" https://api.zrb.dev/v2/tasks
```

**Action:** Replace your auth header construction. Regenerate tokens if your existing keys are v1-only.

---

## 3. Task ID — Integer to UUID

Task `id` is now a UUID string. All URL construction, cache keys, and type-dependent logic that assumed an integer will break.

**Before (v1):**

```typescript
// TypeScript — v1
interface Task {
  id: number;          // integer
  title: string;
  done: boolean;
}
```

**After (v2):**

```typescript
// TypeScript — v2
interface Task {
  id: string;          // UUID e.g. "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  title: string;
  completed: boolean;
}
```

**Action:** Update type definitions. If you stored task IDs in numeric columns or sorted by ID, migrate those data stores to support UUID strings.

---

## 4. Field Rename — `done` to `completed`

The boolean status field is renamed from `done` to `completed`. Both the request body (create/update) and response object are affected.

**Before (v1) — create/update request:**

```bash
curl -X PUT https://api.zrb.dev/tasks/42 \
  -H "X-Auth-Token: sk_abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Ship v2", "done": false}'
```

**After (v2) — create/update request:**

```bash
curl -X PUT https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer zrb2_abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Ship v2", "completed": false}'
```

**Action:** Rename all references to `done` → `completed` in request serialization and response parsing.

---

## 5. Create Task — `project_id` Required

Creating a task now requires `project_id`. Omitting it returns HTTP 422. This is a **required** field with no default.

**Before (v1):**

```json
POST /tasks
{
  "title": "Write tests"
}
```

**After (v2):**

```json
POST /v2/tasks
{
  "title": "Write tests",
  "project_id": "proj_abc123"
}
```

**Action:** Update your create-task UI, CLI, or library call to prompt for or derive a `project_id`. Use the Projects API (if available) to list valid project IDs.

---

## 6. List Endpoints — Paginated Envelope

List endpoints no longer return a bare array. All list responses are wrapped in a paginated envelope. Clients that iterate the response directly as an array will fail.

**Before (v1):**

```javascript
// v1 — bare array, direct iteration
const tasks = await fetch("https://api.zrb.dev/tasks", {
  headers: { "X-Auth-Token": "sk_abc123" }
}).then(r => r.json());

// tasks is an Array — this works
tasks.forEach(t => console.log(t.title));
```

**After (v2):**

```javascript
// v2 — paginated envelope
const res = await fetch("https://api.zrb.dev/v2/tasks", {
  headers: { "Authorization": "Bearer zrb2_abc123" }
}).then(r => r.json());

// res is { items: [...], total: 42, next_cursor: "cursor_xyz" }
res.items.forEach(t => console.log(t.title));

// Paginate if more results exist
if (res.next_cursor) {
  const nextUrl = `https://api.zrb.dev/v2/tasks?cursor=${res.next_cursor}`;
  // fetch the next page...
}
```

**Response envelope structure:**

```json
{
  "items": [...],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

| Field         | Description                                      |
|---------------|--------------------------------------------------|
| `items`       | Array of task objects for the current page       |
| `total`       | Total number of tasks matching the query         |
| `next_cursor` | Cursor for the next page, or `null` if last page |

Pass `?cursor=<next_cursor>&limit=20` (optional, default 20) to fetch subsequent pages.

**Action:** Update all list-response parsing to unwrap `.items`. Add pagination logic if you need to fetch more than one page.

---

## Migration Checklist

Walk through these steps in order.

- [ ] **Regenerate API tokens.** If your tokens are v1-only (`X-Auth-Token`), request new Bearer tokens from the dashboard.
- [ ] **Update auth headers.** Replace `X-Auth-Token` with `Authorization: Bearer` in every request.
- [ ] **Re-point base URLs.** Insert `/v2/` into every endpoint path.
- [ ] **Update type definitions.** Change `id` from `number` to `string` (UUID). Rename `done` → `completed`.
- [ ] **Update read paths.** Search your codebase for `task.done` / `["done"]` — replace with `completed`.
- [ ] **Update write paths.** Fix all Create/Update request bodies to use `completed` instead of `done`, and include `project_id` on creates.
- [ ] **Update list parsing.** Change bare-array iteration to unwrap `response.items`. Add cursor-based pagination if needed.
- [ ] **Migrate stored data.** If you persist task IDs locally (cache, database, local state), convert them to UUID strings.
- [ ] **Add `project_id` logic.** Determine how you'll derive or collect `project_id` on task creation (user prompt, default project, or a lookup).
- [ ] **Run integration tests.** Verify every CRUD path against v2 before deploying.

---

## Upgrade Command

```bash
npm install zrb-client@latest    # Node / TypeScript
pip install --upgrade zrb-client # Python
go get zrb.dev/client@latest     # Go
```

Consult your client library's changelog for any additional language-specific breaking changes.
