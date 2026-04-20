# Zrb v1 → v2 Migration Guide

This guide covers **every breaking change** between Zrb Task API v1 and v2, with **before/after** examples.

---

## Quick map (v1 → v2)

- Base path: `/tasks` → `/v2/tasks`
- Auth: `X-Auth-Token` → `Authorization: Bearer …`
- Task identifier: `id: int` → `id: uuid string`
- Status field: `done` → `completed`
- Create task: `title` only → `title + project_id` (required)
- List responses: bare JSON array → paginated envelope `{ items, total, next_cursor }`

---

## Breaking change 1: All endpoints are now prefixed with `/v2/`

**What changed**

Every endpoint moved under the `/v2/` prefix.

- v1: `GET /tasks`
- v2: `GET /v2/tasks`

**Impact**

Hard-coded URLs will 404 or hit the wrong API version. Update your route builder / base URL constant.

**Before (v1)**

```bash
curl -sS https://api.example.com/tasks
```

**After (v2)**

```bash
curl -sS https://api.example.com/v2/tasks
```

---

## Breaking change 2: Authentication header changed (`X-Auth-Token` → Bearer token)

**What changed**

v1 used an API key header:

- `X-Auth-Token: <your_api_key>`

v2 requires a Bearer token:

- `Authorization: Bearer <your_api_token>`

Requests using `X-Auth-Token` will receive **HTTP 401**.

**Before (v1)**

```bash
curl -sS \
  -H 'X-Auth-Token: YOUR_KEY' \
  https://api.example.com/tasks
```

**After (v2)**

```bash
curl -sS \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  https://api.example.com/v2/tasks
```

---

## Breaking change 3: Task `id` changed type (integer → UUID string)

**What changed**

- v1 task id:
  - `"id": 42`
- v2 task id:
  - `"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"`

**Impact**

- If you parse `id` as an integer, it will fail.
- If you store ids in a numeric DB column, you must migrate to string/UUID.
- Any client-side routing that assumes integers (e.g., `/tasks/42`) must accept UUIDs.

**Before (v1)**

```http
GET /tasks/42
```

```json
{"id": 42, "title": "Write tests", "done": false, "created_at": "2024-01-15T10:30:00Z"}
```

**After (v2)**

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Breaking change 4: Task field renamed (`done` → `completed`)

**What changed**

The boolean status field is renamed:

- v1: `done`
- v2: `completed`

**Impact**

- Deserialization/mapping code must be updated.
- Update payloads must use `completed` (sending `done` won’t update the field as intended).

**Before (v1) — update status**

```bash
curl -sS -X PUT \
  -H 'X-Auth-Token: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"done": true}' \
  https://api.example.com/tasks/42
```

**After (v2) — update status**

```bash
curl -sS -X PUT \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"completed": true}' \
  https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Breaking change 5: Task creation now requires `project_id`

**What changed**

Creating a task now requires a project association:

- v1 request body: `{ "title": "…" }`
- v2 request body: `{ "title": "…", "project_id": "proj_…" }`

Omitting `project_id` returns **HTTP 422**.

**Impact**

- Your UI/service must choose a project for new tasks.
- Any background jobs that create tasks must be updated to supply `project_id`.

**Before (v1)**

```bash
curl -sS -X POST \
  -H 'X-Auth-Token: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title"}' \
  https://api.example.com/tasks
```

**After (v2)**

```bash
curl -sS -X POST \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title", "project_id":"proj_abc123"}' \
  https://api.example.com/v2/tasks
```

---

## Breaking change 6: List endpoints now return a paginated envelope (not a bare array)

**What changed**

- v1 `GET /tasks` returned a **bare array**.
- v2 `GET /v2/tasks` returns an envelope:

```json
{
  "items": [ ... ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, pass `?cursor=<next_cursor>`.

**Impact**

- Code that assumes the response is an array must be updated to read `items`.
- Any custom pagination logic should switch to cursor-based pagination.

**Before (v1)**

```bash
curl -sS \
  -H 'X-Auth-Token: YOUR_KEY' \
  https://api.example.com/tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2)**

```bash
curl -sS \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  'https://api.example.com/v2/tasks?limit=20'
```

```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Buy milk",
      "completed": false,
      "project_id": "proj_abc123",
      "created_at": "..."
    }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**After (v2) — fetch next page**

```bash
curl -sS \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  'https://api.example.com/v2/tasks?cursor=cursor_xyz&limit=20'
```

---

## Step-by-step migration checklist

1. **Update base URLs** to include the `/v2/` prefix for every endpoint you call.
2. **Switch authentication**:
   - Stop sending `X-Auth-Token`.
   - Send `Authorization: Bearer <token>` on every request.
3. **Update Task model**:
   - Change `id` type from integer to string/UUID.
   - Rename `done` → `completed` everywhere (model, serializers, UI).
   - Add `project_id` to the task shape.
4. **Update create-task flows**:
   - Ensure `project_id` is always supplied.
   - Handle `422` responses for missing/invalid `project_id`.
5. **Update list-task handling**:
   - Parse `{ items, total, next_cursor }` instead of an array.
   - Implement cursor-based pagination using `?cursor=<next_cursor>`.
6. **Search & replace / regression check**:
   - Grep for `/tasks` usage that lacks `/v2/`.
   - Grep for `X-Auth-Token`.
   - Grep for `.done` / `"done"`.
   - Verify any routing/ID validation accepts UUIDs.
7. **Run your integration tests** against v2 endpoints and confirm:
   - create/update/get/delete all work
   - pagination works end-to-end

---

## Upgrade command

```bash
zrb upgrade --major
```
