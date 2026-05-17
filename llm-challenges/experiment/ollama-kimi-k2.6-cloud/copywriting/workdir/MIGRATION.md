# Zrb CLI v1 to v2 Migration Guide

Zrb v2 introduces projects, cursor-based pagination, and stricter authentication. This guide covers every breaking change and shows you exactly what to update in your codebase.

---

## Breaking Change 1: Base URL Prefix

All endpoints are now prefixed with `/v2/`.

### Before (v1)
```bash
curl https://api.zrb.io/tasks
curl https://api.zrb.io/tasks/42
curl -X POST https://api.zrb.io/tasks
curl -X PUT https://api.zrb.io/tasks/42
curl -X DELETE https://api.zrb.io/tasks/42
```

### After (v2)
```bash
curl https://api.zrb.io/v2/tasks
curl https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl -X POST https://api.zrb.io/v2/tasks
curl -X PUT https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
curl -X DELETE https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Action:** Update your base URL or prepend `/v2` to every task endpoint path.

---

## Breaking Change 2: Authentication Header

The `X-Auth-Token` header is removed. v2 requires a Bearer token in the `Authorization` header. Requests using `X-Auth-Token` will receive HTTP 401.

### Before (v1)
```bash
curl -H "X-Auth-Token: <your_api_key>" \
     https://api.zrb.io/tasks
```

### After (v2)
```bash
curl -H "Authorization: Bearer <your_api_token>" \
     https://api.zrb.io/v2/tasks
```

**Action:** Replace `X-Auth-Token` with `Authorization: Bearer` in all request headers.

---

## Breaking Change 3: Task `id` Type Changed to UUID

Task identifiers changed from auto-incrementing integers to UUID strings. This affects all endpoints that accept or return a task `id`.

### Before (v1)
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Action:** Update your models and validation logic to treat `id` as a UUID string instead of an integer.

---

## Breaking Change 4: Field `done` Renamed to `completed`

The boolean flag on task objects is now named `completed`. Using `done` in request bodies will be ignored or rejected.

### Before (v1)
```json
{
  "title": "Updated title",
  "done": true
}
```

### After (v2)
```json
{
  "title": "Updated title",
  "completed": true
}
```

**Action:** Rename all references from `done` to `completed` in payloads, deserializers, and UI bindings.

---

## Breaking Change 5: Task Creation Requires `project_id`

Creating a task now requires a `project_id`. Omitting it returns HTTP 422.

### Before (v1)
```bash
curl -X POST https://api.zrb.io/tasks \
     -H "Content-Type: application/json" \
     -H "X-Auth-Token: <your_api_key>" \
     -d '{"title": "New task title"}'
```

### After (v2)
```bash
curl -X POST https://api.zrb.io/v2/tasks \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_token>" \
     -d '{
       "title": "New task title",
       "project_id": "proj_abc123"
     }'
```

**Action:** Update all task creation calls to include a valid `project_id`.

---

## Breaking Change 6: List Endpoints Return Paginated Envelope

`GET /v2/tasks` no longer returns a bare array. It now returns a paginated envelope containing `items`, `total`, and `next_cursor`.

### Before (v1)
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2)
```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v1", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, pass the cursor as a query parameter:

```bash
curl "https://api.zrb.io/v2/tasks?cursor=cursor_xyz&limit=20" \
     -H "Authorization: Bearer <your_api_token>"
```

**Action:** Update list consumers to extract tasks from the `items` key and implement cursor-based pagination using `next_cursor`.

---

## Migration Checklist

Use this checklist to roll out the upgrade safely.

- [ ] **1. Update base URL** — Prepend `/v2` to all task endpoint paths.
- [ ] **2. Rotate auth headers** — Replace `X-Auth-Token` with `Authorization: Bearer <token>`.
- [ ] **3. Migrate `id` fields** — Ensure task IDs are stored and validated as UUID strings, not integers.
- [ ] **4. Rename `done` to `completed`** — Update all request payloads, response parsers, and UI state.
- [ ] **5. Add `project_id` to creation** — Every `POST /v2/tasks` call must include a `project_id`.
- [ ] **6. Implement pagination** — Replace bare-array list handling with the paginated envelope (`items`, `total`, `next_cursor`).
- [ ] **7. Run integration tests** — Verify reads, writes, updates, deletes, and list pagination against the v2 sandbox.
- [ ] **8. Deploy and monitor** — Watch for HTTP 401 (auth), HTTP 422 (missing `project_id`), and deserialization errors.

---

## Upgrade Command

Install the latest v2 CLI:

```bash
pip install --upgrade zrb-cli>=2.0.0
```

After upgrading, run `zrb --version` to confirm you are on v2.
