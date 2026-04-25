# Zrb CLI v1 → v2 Migration Guide

This guide covers every breaking change between Zrb CLI v1 and v2 and provides before/after examples to help you upgrade quickly.

---

## 1. API Version Prefix

All endpoints are now namespaced under `/v2/`.

**v1:**
```bash
curl https://api.zrb.example/tasks
curl https://api.zrb.example/tasks/42
```

**v2:**
```bash
curl https://api.zrb.example/v2/tasks
curl https://api.zrb.example/v2/tasks/42
```

---

## 2. Authentication Header

The `X-Auth-Token` header is no longer accepted. v2 requires a standard Bearer token.

**v1:**
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.example/tasks
```

**v2:**
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.example/v2/tasks
```

> **Warning:** Requests using `X-Auth-Token` will receive HTTP 401.

---

## 3. Task ID Type Changed from Integer to UUID

`id` is now a UUID string instead of an integer. This affects every endpoint that references a task by ID and any client-side data models that stored `id` as a number.

**v1:**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**v2:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

> **Action required:** Update any client-side types (e.g., TypeScript `number` → `string`), database columns, or URL builders that assumed integer IDs.

---

## 4. Task Field `done` Renamed to `completed`

The status field on task objects has been renamed. The old name is no longer accepted in request bodies or returned in responses.

**v1:**
```bash
curl -X PUT https://api.zrb.example/tasks/42 \
  -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated title", "done": true}'
```

**v2:**
```bash
curl -X PUT https://api.zrb.example/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated title", "completed": true}'
```

> **Action required:** Rename all references to `done` (request payloads, response parsing, UI bindings) to `completed`.

---

## 5. Task Creation Requires `project_id`

Creating a task now requires a `project_id`. Omitting it returns HTTP 422.

**v1:**
```bash
curl -X POST https://api.zrb.example/tasks \
  -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task title"}'
```

**v2:**
```bash
curl -X POST https://api.zrb.example/v2/tasks \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New task title",
    "project_id": "proj_abc123"
  }'
```

> **Action required:** Ensure your task creation flows capture or provide a `project_id`. If your application does not yet model projects, you must create at least one project and associate every new task with it.

---

## 6. List Endpoints Return a Paginated Envelope

`GET /tasks` previously returned a bare array. v2 returns a paginated envelope with `items`, `total`, and `next_cursor`.

**v1:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**v2:**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-f6a7-8901-bcde-f23456789012", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Use `?cursor=<next_cursor>` to fetch subsequent pages and `?limit=<n>` (default 20) to control page size.

**v2:**
```bash
curl "https://api.zrb.example/v2/tasks?limit=20" \
  -H "Authorization: Bearer <your_api_token>"

curl "https://api.zrb.example/v2/tasks?limit=20&cursor=cursor_xyz" \
  -H "Authorization: Bearer <your_api_token>"
```

> **Action required:** Update any list-rendering logic to read from `response.items` instead of the top-level array, and implement pagination using `next_cursor`.

---

## Migration Checklist

Use this checklist to track your upgrade.

- [ ] **Upgrade CLI** — run the upgrade command (see below).
- [ ] **Update base URL** — add `/v2/` to all API paths.
- [ ] **Rotate auth header** — replace `X-Auth-Token` with `Authorization: Bearer <token>`.
- [ ] **Migrate task ID types** — change task `id` from `integer` to `string` (UUID) in types, schemas, and storage.
- [ ] **Rename `done` → `completed`** — update request payloads, response parsing, and UI bindings.
- [ ] **Integrate projects** — create projects and ensure all new tasks include `project_id`.
- [ ] **Adopt pagination envelope** — update list endpoints to read `items`, `total`, and `next_cursor`.
- [ ] **Run integration tests** — verify end-to-end flows against the v2 API.
- [ ] **Deprecate v1 callers** — remove or sunset any remaining v1 clients.

---

## Upgrade Command

Install the latest v2 CLI:

```bash
zrb upgrade --to=v2
```
