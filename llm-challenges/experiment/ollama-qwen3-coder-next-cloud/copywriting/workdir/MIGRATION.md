# Zrb CLI v2 Migration Guide

This guide covers all breaking changes from Zrb CLI v1 to v2. After upgrading, your existing v1 integration will break until you apply these changes.

---

## What's New in v2

- All endpoints are now prefixed with `/v2/`
- Authentication uses Bearer tokens (JWT-style)
- Task IDs are UUID strings instead of integers
- Task completion status renamed from `done` to `completed`
- Projects introduced—tasks now require a `project_id`
- Pagination via cursor-based list responses instead of bare arrays

---

## Breaking Changes

### 1. Endpoint Path Prefix

All endpoints now require the `/v2/` prefix.

#### Before (v1)
```bash
GET /tasks
POST /tasks
GET /tasks/42
PUT /tasks/42
DELETE /tasks/42
```

#### After (v2)
```bash
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication Header

The authentication header changed from `X-Auth-Token` to `Authorization: Bearer`.

#### Before (v1)
```bash
curl \
  -H "X-Auth-Token: your_api_key" \
  https://api.zrb.dev/v1/tasks
```

#### After (v2)
```bash
curl \
  -H "Authorization: Bearer your_api_token" \
  https://api.zrb.dev/v2/tasks
```

**Note:** Requests using `X-Auth-Token` will receive HTTP 401.

---

### 3. Task ID Type Change

Task IDs are now UUID strings instead of integers.

#### Before (v1)
```json
{
  "id": 42,
  "title": "Ship v1",
  "done": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### After (v2)
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v1",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

All existing integer IDs must be replaced with UUIDs. The API will return HTTP 404 for existing v1-style numeric task IDs.

---

### 4. Field Name: `done` → `completed`

The boolean field `done` has been renamed to `completed`.

#### Before (v1)
```json
{
  "title": "Buy milk",
  "done": false
}
```

#### After (v2)
```json
{
  "title": "Buy milk",
  "completed": false
}
```

Sending `done` in v2 requests will be ignored.

---

### 5. Required `project_id` on Task Creation

Task creation now requires a `project_id`. Omitting it returns HTTP 422.

#### Before (v1)
```bash
curl -X POST https://api.zrb.dev/v1/tasks \
  -H "X-Auth-Token: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

#### After (v2)
```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

---

### 6. Paginated List Response

The `/tasks` list endpoint returns a paginated envelope instead of a bare array.

#### Before (v1)
**Response:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

#### After (v2)
**Response:**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123"},
    {"id": "b2c3d4e5-f678-9012-bcde-f23456789012", "title": "Ship v1", "completed": true, "project_id": "proj_abc123"}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

To fetch the next page, pass `?cursor=cursor_xyz` as a query parameter.

---

## Migration Checklist

Use this checklist to track your migration progress:

- [ ] **Update all endpoint URLs** — prefix with `/v2/`
- [ ] **Switch authentication** — replace `X-Auth-Token` with `Authorization: Bearer <token>`
- [ ] **Refresh task ID handling** — update code to:
  - Accept UUID strings instead of integers
  - Replace any hard-coded integer IDs with generated UUIDs or lookups
- [ ] **Rename fields** — change all `done` to `completed` in request/response payloads
- [ ] **Add project IDs** — create projects (via the CLI or web UI) and include `project_id` on all task creation requests
- [ ] **Implement pagination** — process list responses using the envelope structure:
  - Extract `items` array instead of treating the response as a direct array
  - Follow `next_cursor` for subsequent pages
- [ ] **Update error handling** — anticipate:
  - HTTP 422 on task creation if `project_id` is missing
  - HTTP 404 if referencing tasks by integer ID
  - HTTP 401 if still using `X-Auth-Token`
- [ ] **Test end-to-end** — verify create, read, update, delete workflows work with v2 endpoints
- [ ] **Update SDKs/wrappers** — if you maintain a client library, update version constraints and update examples

---

## Upgrade Command

Run the following to upgrade to v2 of the Zrb CLI:

```bash
npm install -g @zrb/cli@v2
```

Or with Homebrew:

```bash
brew install zrb/tap/zrb && brew upgrade zrb
```

After upgrading, verify the version:

```bash
zrb --version
# Expected: v2.x.x
```