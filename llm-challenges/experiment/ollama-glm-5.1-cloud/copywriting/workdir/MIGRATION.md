# Migrating from Zrb Task API v1 to v2

v2 introduces projects, cursor-based pagination, and stricter authentication. These improvements require several breaking changes. This guide covers every breaking change with before/after examples so you can update your integration quickly.

---

## 1. Endpoint paths now require `/v2/` prefix

All endpoints moved under `/v2/`. Requests to the old paths will 404.

**Before (v1):**

```bash
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**

```bash
GET /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Action:** Update your base URL or path prefix. If you use a constant for the API root, change it from `/tasks` to `/v2/tasks` (or from `https://api.example.com/tasks` to `https://api.example.com/v2/tasks`).

---

## 2. Authentication header changed

The `X-Auth-Token` header is removed. Using it returns **HTTP 401**.

**Before (v1):**

```bash
curl -H "X-Auth-Token: abc123" https://api.example.com/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer abc123" https://api.example.com/v2/tasks
```

**Action:** Replace all `X-Auth-Token` headers with `Authorization: Bearer <token>`. If you use an HTTP client with interceptors or middleware, update the header name there.

---

## 3. Task `id` changed from integer to UUID string

Task IDs are now UUIDs instead of integers. Any code that stores, validates, or type-checks IDs as integers will break.

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

- Change ID fields in your data models and database schemas from integer to string (UUID).
- Update any URL-building logic that interpolates IDs — they are now longer strings and must be URL-encoded if used in query parameters.
- Remove any integer-only validation (e.g., `z.int()` in Zod, `type: integer` in JSON Schema).

---

## 4. Task field `done` renamed to `completed`

The boolean field `done` is now `completed`.

**Before (v1):**

```json
{
  "title": "Ship v2",
  "done": true
}
```

**After (v2):**

```json
{
  "title": "Ship v2",
  "completed": true
}
```

**Action:** Do a project-wide find-and-replace of `done` → `completed` in:

- Task data models / interfaces
- Serialization / deserialization maps
- Conditions and filters (e.g., `if task.done` → `if task.completed`)
- Update request bodies (`{ "done": true }` → `{ "completed": true }`)

---

## 5. Task creation requires `project_id`

`POST /v2/tasks` now **requires** a `project_id` field. Omitting it returns **HTTP 422**.

**Before (v1):**

```bash
curl -X POST https://api.example.com/tasks \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

**After (v2):**

```bash
curl -X POST https://api.example.com/v2/tasks \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

**Action:** Add `project_id` to every task creation call. Determine which project a task belongs to and pass the ID at creation time. If you don't yet have projects set up, create them first via the projects API.

---

## 6. List endpoints return a paginated envelope

`GET /v2/tasks` no longer returns a bare array. It returns an envelope with `items`, `total`, and `next_cursor`.

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
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v2", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Fetch the next page with `GET /v2/tasks?cursor=cursor_xyz`.

**Action:**

- Update deserialization: the response is now an object, not an array. Access tasks via `response.items` instead of iterating the response directly.
- Implement cursor-based pagination if you need to fetch all tasks. Loop until `next_cursor` is `null` or absent.
- Remove any offset/limit pagination logic — v2 uses cursor-based pagination exclusively.

---

## Migration Checklist

- [ ] **Update base URL** — add `/v2/` prefix to all endpoint paths.
- [ ] **Update auth header** — replace `X-Auth-Token` with `Authorization: Bearer <token>`.
- [ ] **Change ID type** — update data models from integer to UUID string.
- [ ] **Rename `done` → `completed`** — update all models, request bodies, and conditionals.
- [ ] **Add `project_id`** to all task creation requests; handle HTTP 422 when missing.
- [ ] **Update list response parsing** — read tasks from `response.items` instead of the root array.
- [ ] **Implement cursor pagination** — loop using `next_cursor` to fetch all pages.
- [ ] **Remove offset/limit pagination** — v2 uses `cursor` and `limit`, not `offset`.
- [ ] **Remove `X-Auth-Token` from tests and fixtures** — they will 401.
- [ ] **Run integration tests** against v2 to confirm all changes.

---

## Upgrade

```bash
npm install zrb@2     # or: pip install zrb==2.0.0
```