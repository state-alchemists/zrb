# Migrating from Zrb API v1 to v2

Zrb API v2 introduces projects, cursor-based pagination, and stricter authentication — along with several breaking changes. This guide covers every change, with before/after examples, so you can migrate your client code with confidence.

---

## Breaking Changes at a Glance

| # | Change | Impact |
|---|--------|--------|
| 1 | Endpoint prefix `/v2/` | All URLs change |
| 2 | Auth header: `X-Auth-Token` → `Authorization: Bearer` | All requests rejected if stale |
| 3 | Task `id`: integer → UUID string | All `id` lookups and references break |
| 4 | Field `done` → `completed` | All reads and writes of task status |
| 5 | `project_id` required on create | Create requests without it return 422 |
| 6 | List responses: bare array → paginated envelope | All list consumers need unwrapping |

---

## 1. Endpoint Prefix: `/v2/`

All endpoints now live under `/v2/`. Requests to v1 paths return 404.

**Before (v1)**

```bash
curl https://api.zrb.dev/tasks
curl https://api.zrb.dev/tasks/42
curl https://api.zrb.dev/tasks -X POST -d '{"title": "..."}'
```

**After (v2)**

```bash
curl https://api.zrb.dev/v2/tasks
curl https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl https://api.zrb.dev/v2/tasks -X POST -d '{"title": "...", "project_id": "proj_abc123"}'
```

**Action:** Update your base URL or path prefix to append `/v2`.

---

## 2. Authentication: Bearer Token

The `X-Auth-Token` header is removed. All requests must use a Bearer token via the `Authorization` header. Sending the old header returns HTTP 401.

**Before (v1)**

```http
X-Auth-Token: sk_live_abc123
```

**After (v2)**

```http
Authorization: Bearer sk_live_abc123
```

**Action:** Replace the `X-Auth-Token` header with `Authorization: Bearer <token>`. Token values themselves remain the same — only the transport changed.

---

## 3. Task ID: Integer → UUID String

Task identifiers are now UUID v4 strings. All endpoints that accept an `id` parameter must use the new format. Existing integer IDs from v1 snapshots are invalid — re-fetch your task list from v2 to obtain the new UUIDs.

**Before (v1)**

```python
# Python — lookup by integer
response = client.get(f"/tasks/{task_id}")  # task_id = 42
```

**After (v2)**

```python
# Python — lookup by UUID string
response = client.get(f"/v2/tasks/{task_id}")  # task_id = "a1b2c3d4-..."
```

**Actions:**
- Migrate stored references (database columns, config files, cache keys) from integer to UUID string.
- Re-fetch any v1 task lists you need to carry forward — the v2 list response contains the new UUIDs.
- Update any schema or type definitions from `int` to `string`.
- URL templates or route builders that cast `id` to `int` must be updated to handle strings.

---

## 4. Field Rename: `done` → `completed`

The task status field is renamed. The semantics are identical — it is `false` (incomplete) or `true` (complete). v2 still accepts `done` in request bodies? **No.** It returns HTTP 422 if you send `done`.

**Before (v1)**

```json
// Response payload
{"id": 42, "title": "Ship v1", "done": true, "created_at": "..."}
```

```python
# Client code reading status
if task["done"]:
    print("Complete!")
```

**After (v2)**

```json
// Response payload
{"id": "a1b2c3d4-...", "title": "Ship v1", "completed": true, "created_at": "..."}
```

```python
# Client code reading status
if task["completed"]:
    print("Complete!")
```

**Update writes too:**

**Before (v1)**

```bash
curl -X PUT https://api.zrb.dev/tasks/42 \
  -d '{"done": true}'
```

**After (v2)**

```bash
curl -X PUT https://api.zrb.dev/v2/tasks/a1b2c3d4-... \
  -d '{"completed": true}'
```

**Actions:**
- Search your codebase for all references to `done` in the context of task objects.
- Update reads: `task["done"]` → `task["completed"]`.
- Update writes: `{"done": true}` → `{"completed": true}`.
- Update TypeScript/Python/Go type definitions and serializers.
- Update any UI logic that maps the field name.

---

## 5. `project_id` Required on Create

Every task must belong to a project. The `project_id` field is required in `POST /v2/tasks`. Omitting it returns HTTP 422 with a validation error.

**Before (v1)**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: sk_live_abc123" \
  -d '{"title": "Buy milk"}'
# → 201 Created
```

**After (v2)**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer sk_live_abc123" \
  -d '{"title": "Buy milk", "project_id": "proj_abc123"}'
# → 201 Created
```

**Actions:**
- Obtain a valid `project_id` from the v2 projects endpoint (or your dashboard).
- Update all task creation code paths to include `project_id`.
- Add the field to request body builders, form validators, and test fixtures.

---

## 6. Paginated List Envelope

List endpoints no longer return a bare array. Every list response is wrapped in a paginated envelope. Clients must unwrap the `items` field and handle cursors for pagination.

**Before (v1)**

```json
// GET /tasks — response
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
// Client code
const tasks = await response.json();       // bare array
tasks.forEach(t => render(t));
```

**After (v2)**

```json
// GET /v2/tasks — response
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "e5f6g7h8-...", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
// Client code
const body = await response.json();
const tasks = body.items;                   // unwrap from envelope
const hasMore = body.next_cursor !== null;  // pagination signal
tasks.forEach(t => render(t));
```

**Pagination workflow:**

```javascript
async function fetchAllTasks(baseUrl) {
  let cursor = null;
  const all = [];
  do {
    const url = cursor
      ? `${baseUrl}?cursor=${cursor}`
      : baseUrl;
    const res = await fetch(url);
    const page = await res.json();
    all.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return all;
}
```

**Actions:**
- Update all list response parsers to access `.items` instead of treating the response as an array.
- Add cursor-based pagination to handle result sets larger than the default page size (20).
- Update TypeScript/OpenAPI/GraphQL type definitions for list responses.

---

## Migration Checklist

Follow these steps in order. Each step maps to one of the six breaking changes above.

- [ ] **1. Endpoints** — Update your base URL or path prefix to include `/v2`.
- [ ] **2. Authentication** — Replace `X-Auth-Token` header with `Authorization: Bearer <token>`.
- [ ] **3. Task IDs** — Re-fetch task data from v2 to get UUIDs. Migrate all stored integer ID references to UUID strings. Update type definitions from `int` to `string`.
- [ ] **4. Status field** — Replace all `done` references with `completed` in reads, writes, type definitions, and UI bindings.
- [ ] **5. Project ID** — Add `project_id` to every task creation call. Obtain your project ID from the v2 projects API or dashboard.
- [ ] **6. Pagination** — Update list response parsers to unwrap `items` from the envelope. Implement cursor-based pagination if you fetch more than 20 items.
- [ ] **Test** — Run your integration test suite against the v2 API. Verify each endpoint, field, and auth flow.
- [ ] **Deploy** — Ship the updated client code. The v1 API will be retired 90 days from the v2 release date.

---

## Upgrade

Install or update to the latest Zrb CLI which includes the v2 API client:

```bash
pip install --upgrade zrb
```

Verify the installation:

```bash
zrb --version
# v2.0.0 or later
```

Need help? Open an issue at https://github.com/state-alchemists/zrb/issues.
