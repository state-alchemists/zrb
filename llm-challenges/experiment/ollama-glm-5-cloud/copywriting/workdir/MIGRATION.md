# Zrb CLI v1 to v2 Migration Guide

This guide covers all breaking changes between Zrb CLI v1 and v2. If you're currently using v1, follow this guide to update your integration.

---

## Breaking Changes Overview

v2 introduces six breaking changes:

1. **Authentication header changed** — `X-Auth-Token` replaced with `Authorization: Bearer`
2. **API prefix added** — All endpoints now require `/v2/` prefix
3. **Task ID type changed** — Integer IDs replaced with UUID strings
4. **Field renamed** — `done` field renamed to `completed`
5. **Required field added** — `project_id` is now mandatory for task creation
6. **List response format changed** — Bare arrays replaced with paginated envelope

---

## Breaking Change 1: Authentication Header

The `X-Auth-Token` header is no longer supported. All requests must use Bearer token authentication.

**Before (v1):**
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.io/tasks
```

**After (v2):**
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.io/v2/tasks
```

Requests using the old `X-Auth-Token` header will receive **HTTP 401 Unauthorized**.

---

## Breaking Change 2: API Path Prefix

All endpoints now require the `/v2/` prefix.

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

---

## Breaking Change 3: Task ID Type

Task IDs have changed from auto-assigned integers to UUID strings.

**Before (v1):**
```json
{
  "id": 42
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Impact:** Any code that assumes integer IDs (e.g., type validation, sorting, URL path construction) must be updated to handle UUID strings.

---

## Breaking Change 4: Field Rename (`done` → `completed`)

The `done` field has been renamed to `completed`.

**Before (v1):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

**Before (v1) — Update request:**
```json
{
  "done": true
}
```

**After (v2) — Update request:**
```json
{
  "completed": true
}
```

**Impact:** Any code referencing `task.done` or sending `{"done": ...}` in update requests must use `completed` instead.

---

## Breaking Change 5: Required `project_id` Field

Task creation now requires a `project_id`. Omitting it returns **HTTP 422 Unprocessable Entity**.

**Before (v1):**
```json
{
  "title": "New task title"
}
```

**After (v2):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Impact:** You must obtain a project ID before creating tasks. Update your workflow to include project assignment at task creation time.

---

## Breaking Change 6: Paginated List Response

List endpoints no longer return bare arrays. They now return a paginated envelope.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v2", "done": true, "created_at": "..."}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc", "created_at": "..."},
    {"id": "c3d4...", "title": "Ship v2", "completed": true, "project_id": "proj_abc", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Impact:**
- Code expecting a bare array must access `response.items`
- Consider implementing pagination with `?cursor=<next_cursor>` to fetch all results
- Use `?limit=N` to control page size (default: 20)

---

## Migration Checklist

Use this checklist to ensure you've addressed all breaking changes:

- [ ] **Update authentication header**
  - Replace `X-Auth-Token: <key>` with `Authorization: Bearer <token>`

- [ ] **Update API endpoints**
  - Add `/v2/` prefix to all API paths

- [ ] **Update task ID handling**
  - Change integer type to string/UUID type in models and validation
  - Update any ID-based sorting or comparison logic

- [ ] **Rename `done` to `completed`**
  - Update response parsing to read `completed` instead of `done`
  - Update update requests to send `completed` instead of `done`

- [ ] **Add `project_id` to task creation**
  - Ensure your workflow includes project ID assignment
  - Update create requests to include `"project_id": "..."`

- [ ] **Update list response handling**
  - Change array handling to access `response.items`
  - Optionally implement pagination using `next_cursor` and `?cursor=` parameter

- [ ] **Test all endpoints**
  - Verify authentication works
  - Test create, read, update, delete operations
  - Validate pagination behavior

---

## Upgrade Command

```bash
zrb upgrade --to v2
```

For issues or questions, consult the [Zrb Documentation](https://docs.zrb.io) or visit our community forum.