# Zrb CLI v2 Migration Guide

This guide helps experienced v1 users migrate to Zrb CLI v2. All breaking changes from v1 to v2 are documented here with before/after code examples.

## Table of Contents

1. [Endpoint Path Changes](#endpoint-path-changes)
2. [Authentication Changes](#authentication-changes)
3. [Task ID Type Change (Integer → UUID String)](#task-id-type-change-integer--uuid-string)
4. [Field Renaming: `done` → `completed`](#field-renaming-done--completed)
5. [Project ID Requirement](#project-id-requirement)
6. [Pagination Changes](#pagination-changes)
7. [Step-by-Step Migration Checklist](#step-by-step-migration-checklist)
8. [Upgrade Command](#upgrade-command)

---

## Endpoint Path Changes

All v2 endpoints are prefixed with `/v2/`.

| v1 Endpoint | v2 Endpoint |
|-------------|-------------|
| `GET /tasks` | `GET /v2/tasks` |
| `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| `POST /tasks` | `POST /v2/tasks` |
| `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

### Example: List Tasks

**Before (v1):**
```bash
curl -X GET https://api.zrb.com/tasks \
  -H "X-Auth-Token: your_api_key"
```

**After (v2):**
```bash
curl -X GET "https://api.zrb.com/v2/tasks?limit=20" \
  -H "Authorization: Bearer your_api_token"
```

---

## Authentication Changes

The authentication header changed from `X-Auth-Token` to Bearer token format.

| v1 | v2 |
|----|----|
| `X-Auth-Token: <your_api_key>` | `Authorization: Bearer <your_api_token>` |

**Before (v1):**
```bash
curl -X GET https://api.zrb.com/tasks \
  -H "X-Auth-Token: sk_live_abc123"
```

**After (v2):**
```bash
curl -X GET https://api.zrb.com/v2/tasks \
  -H "Authorization: Bearer tk_live_abc123"
```

> **Note:** Requests using the old `X-Auth-Token` header will receive HTTP 401.

---

## Task ID Type Change (Integer → UUID String)

Task `id` changed from integer to UUID string format.

| v1 Task ID | v2 Task ID |
|------------|------------|
| `42` | `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` |

**Before (v1):**
```json
{
  "id": 42,
  "title": "Buy milk",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Buy milk",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Example: Get Task

**Before (v1):**
```bash
curl -X GET https://api.zrb.com/tasks/42 \
  -H "X-Auth-Token: sk_live_abc123"
```

**After (v2):**
```bash
curl -X GET "https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer tk_live_abc123"
```

---

## Field Renaming: `done` → `completed`

The `done` field on Task objects was renamed to `completed`.

| v1 Field | v2 Field |
|----------|----------|
| `done` | `completed` |

**Before (v1):**
```bash
curl -X POST https://api.zrb.com/tasks \
  -H "X-Auth-Token: sk_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Ship v1", "done": true}'
```

**After (v2):**
```bash
curl -X POST https://api.zrb.com/v2/tasks \
  -H "Authorization: Bearer tk_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Ship v1", "completed": true, "project_id": "proj_v1_release"}'
```

### Example: Update Task

**Before (v1):**
```bash
curl -X PUT https://api.zrb.com/tasks/42 \
  -H "X-Auth-Token: sk_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{"done": true}'
```

**After (v2):**
```bash
curl -X PUT "https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer tk_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

---

## Project ID Requirement

Task creation now requires a `project_id`. Omitting it returns HTTP 422.

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

### Example: Create Task with Project

**Before (v1):**
```bash
curl -X POST https://api.zrb.com/tasks \
  -H "X-Auth-Token: sk_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write tests"}'
```

**After (v2):**
```bash
curl -X POST https://api.zrb.com/v2/tasks \
  -H "Authorization: Bearer tk_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write tests", "project_id": "proj_test_automation"}'
```

---

## Pagination Changes

List endpoints now return a paginated envelope instead of a bare array.

| v1 Response | v2 Response |
|-------------|-------------|
| `[{...}, {...}]` | `{"items": [...], "total": 42, "next_cursor": "cursor_xyz"}` |

**Before (v1):**
```bash
curl -X GET https://api.zrb.com/tasks \
  -H "X-Auth-Token: sk_live_abc123"
```
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**
```bash
curl -X GET "https://api.zrb.com/v2/tasks?limit=20" \
  -H "Authorization: Bearer tk_live_abc123"
```
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc", "created_at": "..."},
    {"id": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "title": "Ship v1", "completed": true, "project_id": "proj_v1", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

### Example: Fetch Next Page

**After (v2):**
```bash
curl -X GET "https://api.zrb.com/v2/tasks?cursor=cursor_xyz&limit=20" \
  -H "Authorization: Bearer tk_live_abc123"
```

---

## Step-by-Step Migration Checklist

Use this checklist to systematically migrate from v1 to v2:

1. **Update API endpoints**
   - Replace all instances of `/tasks` with `/v2/tasks`
   - Replace all instances of `/tasks/{id}` with `/v2/tasks/{id}`

2. **Update authentication**
   - Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
   - Verify your v2 API token is valid (not the same as v1 key)

3. **Handle Task ID changes**
   - Update code to treat task IDs as strings (not integers)
   - Update any database schemas that stored task IDs
   - Update any logging or tracking that relies on task ID format

4. **Update field names**
   - Replace all occurrences of `done` in request/response bodies with `completed`
   - Update validation schemas and type definitions
   - Update any serialization/deserialization logic

5. **Add project_id to task creation**
   - Ensure all `POST /v2/tasks` requests include `project_id`
   - Update UI forms and CLI commands that create tasks

6. **Implement pagination**
   - Update list endpoint handlers to parse the paginated envelope
   - Implement cursor-based pagination if not already in place
   - Handle `items`, `total`, and `next_cursor` fields appropriately

7. **Update error handling**
   - Expect HTTP 422 when `project_id` is missing in task creation
   - Expect HTTP 401 when using old `X-Auth-Token` header

8. **Test thoroughly**
   - Test all v1 use cases against v2 endpoints
   - Verify backward compatibility with any integrations
   - Monitor logs for any errors during the transition period

---

## Upgrade Command

To upgrade the Zrb CLI to v2:

```bash
npm install -g @zrb/cli@latest
```

Or using Homebrew (macOS/Linux):

```bash
brew install zrb && brew upgrade zrb
```

Verify the version:

```bash
zrb --version
```

Expected output: `zrb/v2.x.x`
