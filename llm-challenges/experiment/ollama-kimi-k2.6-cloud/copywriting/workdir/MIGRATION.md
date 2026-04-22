# Zrb CLI v1 → v2 Migration Guide

This guide covers every breaking change when upgrading from Zrb CLI v1 to v2. It assumes you are already familiar with the v1 API.

---

## 1. API Version Prefix

All endpoints are now prefixed with `/v2/`.

### Before (v1)

```bash
curl -X GET https://api.zrb.example/tasks
```

### After (v2)

```bash
curl -X GET https://api.zrb.example/v2/tasks
```

> Update every hardcoded URL and base path in your HTTP clients, SDK wrappers, and environment configs.

---

## 2. Authentication Header

The custom `X-Auth-Token` header is replaced by a standard Bearer token.

### Before (v1)

```bash
curl -H "X-Auth-Token: <your_api_key>" \
     https://api.zrb.example/tasks
```

### After (v2)

```bash
curl -H "Authorization: Bearer <your_api_token>" \
     https://api.zrb.example/v2/tasks
```

> Requests sent with the old `X-Auth-Token` header will receive **HTTP 401 Unauthorized**.

---

## 3. Task `id` Type Changed to UUID

Task identifiers changed from auto-incrementing integers to UUID strings.

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

> Review any code that treats `id` as an integer (sorting, numeric comparison, SQL joins, or local ID mapping tables).

---

## 4. Task Field Renamed: `done` → `completed`

The boolean field indicating task status is renamed from `done` to `completed`.

### Before (v1)

```json
{
  "title": "Ship release",
  "done": true
}
```

```bash
curl -X PUT https://api.zrb.example/tasks/42 \
     -H "Content-Type: application/json" \
     -H "X-Auth-Token: <your_api_key>" \
     -d '{"done": true}'
```

### After (v2)

```json
{
  "title": "Ship release",
  "completed": true
}
```

```bash
curl -X PUT https://api.zrb.example/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_token>" \
     -d '{"completed": true}'
```

> Any JSON serialization, UI bindings, or database columns referencing `done` must be updated to `completed`.

---

## 5. Task Creation Requires `project_id`

Creating a task now requires a `project_id`. Omitting it returns **HTTP 422 Unprocessable Entity**.

### Before (v1)

```json
POST /tasks
{
  "title": "New task title"
}
```

### After (v2)

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

> Ensure your application has access to a valid `project_id` before invoking task creation. You may need to add a project selection step in your UI or configuration.

---

## 6. Paginated List Response

The list endpoint no longer returns a bare array. It now returns a paginated envelope with `items`, `total`, and `next_cursor`.

### Before (v1)

```bash
curl -H "X-Auth-Token: <your_api_key>" \
     https://api.zrb.example/tasks
```

**Response:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### After (v2)

```bash
curl -H "Authorization: Bearer <your_api_token>" \
     "https://api.zrb.example/v2/tasks?limit=20"
```

**Response:**

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

> Update array iteration logic to read from `response.items`. Implement pagination by passing `?cursor=<next_cursor>` on subsequent requests.

---

## Step-by-Step Migration Checklist

Use this checklist to ensure a complete and safe upgrade.

- [ ] **Install v2 CLI** — run the upgrade command (see below).
- [ ] **Rotate credentials** — generate a new API token if your existing token is tied to v1-only scopes.
- [ ] **Update base URL** — append `/v2/` to all endpoint paths or central API client configuration.
- [ ] **Replace auth header** — swap `X-Auth-Token` for `Authorization: Bearer <token>` in all requests.
- [ ] **Refactor ID handling** — change task `id` storage and comparisons from integer to string (UUID).
- [ ] **Rename `done` → `completed`** — update request bodies, response parsing, and any local model definitions.
- [ ] **Supply `project_id` on create** — update task creation forms, scripts, and tests to include a valid `project_id`.
- [ ] **Adopt pagination envelope** — read tasks from `items`, surface `total`, and implement cursor-based pagination.
- [ ] **Run integration tests** — verify all CRUD operations and list pagination against a v2 endpoint.
- [ ] **Update documentation** — refresh internal wiki pages, OpenAPI specs, and consumer-facing docs.

---

## Upgrade Command

```bash
zrb self-update --version 2
```

After upgrading, confirm the version:

```bash
zrb --version
```

If you encounter issues, downgrade temporarily with:

```bash
zrb self-update --version 1
```
