# Zrb CLI v1 to v2 Migration Guide

This guide helps you migrate your existing v1 integrations to the v2 API.

---

## Overview

Zrb CLI v2 introduces several breaking changes to support projects, improved pagination, and stricter authentication. All v1 endpoints remain functional during the deprecation period, but we recommend migrating soon.

---

## Breaking Changes

### 1. Endpoint URL Prefix

All endpoints are now prefixed with `/v2/`.

**Before (v1):**
```bash
curl https://api.zrb.io/tasks 
curl https://api.zrb.io/tasks/42 
```

**After (v2):**
```bash
curl https://api.zrb.io/v2/tasks 
curl https://api.zrb.io/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 
```

---

### 2. Authentication Header

The authentication header has changed from `X-Auth-Token` to Bearer token format.

**Before (v1):**
```bash
curl -H "X-Auth-Token: <your_api_key>" https://api.zrb.io/tasks 
```

**After (v2):**
```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.io/v2/tasks 
```

Requests using the old `X-Auth-Token` header will receive HTTP 401.

---

### 3. Task ID Type

Task IDs have changed from integers to UUID strings.

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

Update your data models and type definitions to expect string IDs instead of integers.

---

### 4. Task Field Renamed: `done` to `completed`

The boolean field indicating task completion status has been renamed.

**Before (v1):**
```json
// Request body for updating a task
{
  "title": "Updated task",
  "done": true
}

// Response body
{
  "id": 42,
  "title": "Updated task",
  "done": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2):**
```json
// Request body for updating a task
{
  "title": "Updated task",
  "completed": true
}

// Response body
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Updated task",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### 5. Required `project_id` for Task Creation

Creating a task now requires a `project_id` field. Omitting it returns HTTP 422.

**Before (v1):**
```bash
curl -X POST https://api.zrb.io/tasks \
  -H "X-Auth-Token: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task title"}'
```

**After (v2):**
```bash
curl -X POST https://api.zrb.io/v2/tasks \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task title", "project_id": "proj_abc123"}'
```

---

### 6. List Response Format Changed to Paginated Envelope

The list tasks endpoint no longer returns a bare array. It now returns a paginated envelope with `items`, `total`, and optional `next_cursor`.

**Before (v1):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "2024-01-15T10:30:00Z"},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "2024-01-15T11:00:00Z"}
]
```

**After (v2):**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "2024-01-15T10:30:00Z"},
    {"id": "b2c3d4e5-f6a7-8901-bcde-f23456789012", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "2024-01-15T11:00:00Z"}
  ],
  "total": 2,
  "next_cursor": null
}
```

To paginate, pass the `cursor` from `next_cursor` as a query parameter:

```bash
curl "https://api.zrb.io/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer <your_api_token>" 
```

---

## Step-by-Step Migration Checklist

Use this checklist to ensure a complete migration:

- [ ] **Update base URL**: Add `/v2/` prefix to all endpoint paths
- [ ] **Replace authentication header**: Change `X-Auth-Token` to `Authorization: Bearer`
- [ ] **Update ID types**: Change task ID handling from integers to UUID strings
- [ ] **Rename `done` to `completed`**: Update field names in request bodies and response parsing
- [ ] **Add `project_id` to task creation**: Ensure all `POST /v2/tasks` calls include a `project_id`
- [ ] **Update list response parsing**: Handle paginated envelope format (`items`, `total`, `next_cursor`) instead of bare array
- [ ] **Implement pagination**: Add support for cursor-based pagination if your app lists many tasks
- [ ] **Test all endpoints**: Verify GET, POST, PUT, and DELETE operations work correctly
- [ ] **Update documentation**: Reflect API changes in your internal docs
- [ ] **Notify team**: Ensure all developers are aware of the breaking changes

---

## Upgrade Command

Install the latest v2 CLI to get started:

```bash
pip install --upgrade zrb>=2.0.0
```

Or with `uv`:

```bash
uv pip install --upgrade zrb>=2.0.0
```

---

## Need Help?

If you encounter issues during migration:

- Review the full [v2 API spec](v2_spec.md)
- Check the [GitHub issues](https://github.com/state-alchemists/zrb/issues) for known problems
- Join our [Discord community](https://discord.gg/zrb) for real-time support
