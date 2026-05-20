# Zrb API v2 Migration Guide

This document walks you through every breaking change between Zrb Task API v1 and v2. Read it in full before upgrading — each section contains a before/after example to verify against your codebase.

---

## Overview

Zrb v2 introduces projects, pagination, and stricter security conventions. Six areas break backward compatibility:

| # | Change | Impact |
|---|--------|--------|
| 1 | Endpoints prefixed with `/v2/` | All URL strings must be updated |
| 2 | Auth header changed to Bearer token | Client auth logic must be rewritten |
| 3 | Task `id` changed from integer to UUID | Type handling, caching keys, stored references |
| 4 | `done` renamed to `completed` | Response parsing, request bodies |
| 5 | `project_id` required on create | Workflow logic must supply a project |
| 6 | List responses wrapped in paginated envelope | Array indexing, pagination logic |

**Migration time estimate:** 1–3 hours for a typical integration. Follow the checklist at the end.

---

## Breaking Change 1: Endpoint Prefix

All endpoints now live under `/v2/`.

**Before (v1):**

```
GET /tasks
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**

```
GET /v2/tasks
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

Update your base URL or route prefix. Old paths return HTTP 404.

---

## Breaking Change 2: Authentication Header

The auth header changed from a custom `X-Auth-Token` to the standard Bearer scheme. Old requests receive HTTP 401.

**Before (v1):**

```
X-Auth-Token: sk-abc123
```

**After (v2):**

```
Authorization: Bearer sk-abc123
```

Replace any `X-Auth-Token` header construction with `Authorization: Bearer <token>`. Token values themselves remain the same — no need to regenerate.

---

## Breaking Change 3: Task `id` Type (Integer → UUID)

Task identifiers are now UUID strings instead of auto-incrementing integers. Existing tasks retain their UUIDs; any v1 integer IDs are invalid in v2.

**Before (v1) — task object:**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2) — task object:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Check all places that assume numeric IDs:

- URL construction: `GET /v2/tasks/${taskId}` — now a UUID, but string interpolation still works.
- Type coercion: parsing `response.id` as `Number`/`int` will now break. Treat as string.
- Local caching keys, in-memory maps, sorted sets — switch to string keys.
- Stored references (database, localStorage) — re-fetch or migrate.

---

## Breaking Change 4: `done` Renamed to `completed`

The `done` field is renamed to `completed` in both responses **and** request bodies. The old field no longer appears.

**Before (v1) — creating a task:**

```json
POST /tasks

{
  "title": "Write tests"
}
```

Response includes `"done": false`.

**After (v2) — creating a task:**

```json
POST /v2/tasks

{
  "title": "Write tests",
  "project_id": "proj_abc123"
}
```

Response includes `"completed": false`.

**Before (v1) — marking a task complete:**

```json
PUT /tasks/42

{
  "done": true
}
```

**After (v2) — marking a task complete:**

```json
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890

{
  "completed": true
}
```

Search your codebase for `done` in API-related code and replace with `completed`. Do not send both — the server ignores `done` silently.

---

## Breaking Change 5: `project_id` Required on Create

Task creation now requires a `project_id`. Omitting it returns HTTP 422 with a validation error.

**Before (v1):**

```json
POST /tasks

{
  "title": "New task"
}
```

**After (v2):**

```json
POST /v2/tasks

{
  "title": "New task",
  "project_id": "proj_abc123"
}
```

**What to do:**

1. Design a project onboarding flow if your app doesn't have one yet.
2. Assign a default project for users who don't explicitly choose one.
3. Update your task creation UI and API calls to include `project_id`.

---

## Breaking Change 6: List Responses Now Paginated

`GET /v2/tasks` no longer returns a bare array. It returns a paginated envelope. The same applies to any future list endpoints.

**Before (v1):**

```
GET /tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**

```
GET /v2/tasks?limit=20&cursor=
```

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_...", "created_at": "..."},
    {"id": "b3c4...", "title": "Ship v1", "completed": true, "project_id": "proj_...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Updates required:**

- Replace bare-array indexing with `response.items` (e.g., `res.items` not `res`).
- Update type definitions to expect `{ items: Task[], total: number, next_cursor: string }`.
- Implement cursor-based pagination: pass `?cursor=<next_cursor>` for each subsequent page.
- Use `total` for count displays and `next_cursor` being non-empty for "has more" checks.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `cursor` | string | — | Pagination cursor from previous response |
| `limit` | integer | 20 | Max items per page (1–100) |

---

## Step-by-Step Migration Checklist

1. **Update endpoint URLs.** Replace all `/tasks` with `/v2/tasks`.
2. **Update auth headers.** Change `X-Auth-Token` to `Authorization: Bearer`.
3. **Add `project_id` to task creation.** Determine how your app obtains or defaults a project ID.
4. **Replace `done` with `completed`.** Update response deserialization and request body construction everywhere.
5. **Handle UUID IDs.** Remove integer assumptions — cast to string, update cache keys and stored references.
6. **Wrap list-response parsing.** Read `response.items` instead of the raw array. Add pagination support.
7. **Test each endpoint.** Verify GET, POST, PUT, DELETE against v2. Confirm 401 on old auth, 422 on missing `project_id`, 404 on old integer IDs.
8. **Remove dead code.** Delete any v1-only fallbacks once migration is verified.

---

## Upgrade Command

```bash
npm install zrb@latest        # JavaScript / TypeScript
pip install --upgrade zrb     # Python
```