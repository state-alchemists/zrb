# Zrb CLI v1 → v2 Migration Guide

v2 introduces projects, improved pagination, and stricter auth. This guide covers every breaking change and how to update your integration.

---

## Breaking Changes at a Glance

| # | Change | Impact |
|---|--------|--------|
| 1 | All endpoints prefixed with `/v2/` | Update all URL paths |
| 2 | Auth header: `X-Auth-Token` → `Bearer` | Update request headers |
| 3 | Task `id` changed from integer to UUID | Update ID handling |
| 4 | Field `done` renamed to `completed` | Update field references |
| 5 | Create requires `project_id` | Pass project on task creation |
| 6 | List returns paginated envelope | Update response parsing |

---

## 1. Endpoint Prefix Change

All endpoints now live under `/v2/`. Requests to v1 paths will return `404`.

**Before (v1):**
```
GET /tasks
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**
```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication Header

The auth header has changed from a custom header to a standard Bearer token. Requests using `X-Auth-Token` will receive `401 Unauthorized`.

**Before (v1):**
```http
X-Auth-Token: your_api_key_here
```

**After (v2):**
```http
Authorization: Bearer your_api_token_here
```

---

## 3. Task ID Type Change

Task `id` is now a UUID string instead of an integer. Update any code that expects an integer ID or parses IDs numerically.

**Before (v1):**
```json
{ "id": 42, "title": "Write tests", "done": false, "created_at": "..." }
```

**After (v2):**
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false, "project_id": "proj_abc123", "created_at": "..." }
```

Update ID handling in:
- URL path parameters
- State management
- Database storage (change column type)
- Any integer assumptions (e.g., sorting, comparison logic)

---

## 4. Field Renamed: `done` → `completed`

The task completion status field has been renamed. Update all field references.

**Before (v1):**
```json
{ "title": "Ship v1", "done": true }
```

**After (v2):**
```json
{ "title": "Ship v2", "completed": true }
```

Also applies to response bodies and any conditional logic checking task status.

---

## 5. Task Creation Requires `project_id`

Creating a task now requires a `project_id`. Omitting it returns `422 Unprocessable Entity`.

**Before (v1):**
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title"
}
```

**After (v2):**
```http
POST /v2/tasks
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

You must provision at least one project before creating tasks. Projects are created via the Projects API (out of scope for this guide—refer to the Projects documentation).

---

## 6. List Response: Paginated Envelope

List endpoints no longer return a bare array. They return a paginated envelope containing `items`, `total`, and `next_cursor`.

**Before (v1):**
```json
[
  { "id": 1, "title": "Buy milk", "done": false, "created_at": "..." },
  { "id": 2, "title": "Ship v1", "done": true, "created_at": "..." }
]
```

**After (v2):**
```json
{
  "items": [
    { "id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..." },
    { "id": "e5f6a7b8-...", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..." }
  ],
  "total": 2,
  "next_cursor": null
}
```

**Pagination usage:**
```
GET /v2/tasks?limit=20
GET /v2/tasks?limit=20&cursor=cursor_xyz
```

Update your response parsing to extract `items` from the envelope rather than using the response directly as an array.

---

## Migration Checklist

- [ ] Update all endpoint URLs from `/tasks` to `/v2/tasks`
- [ ] Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
- [ ] Change task ID handling from integer to UUID string
- [ ] Rename all `done` field references to `completed`
- [ ] Ensure every task creation request includes a valid `project_id`
- [ ] Update list response parsing to handle the paginated envelope
- [ ] Add pagination support using `cursor` and `limit` query params
- [ ] Update any database columns storing task IDs (integer → UUID)
- [ ] Update any client-side ID generation logic
- [ ] Test all integrations against the v2 endpoint

---

## Upgrade Command

Once your code is updated, point your client to v2:

```bash
# Update your Zrb CLI configuration
zb config set api_version v2
zb config set auth_token YOUR_NEW_API_TOKEN
```

Or update your environment:
```bash
export ZRB_API_VERSION=v2
export ZRB_AUTH_TOKEN=your_new_token_here
```
