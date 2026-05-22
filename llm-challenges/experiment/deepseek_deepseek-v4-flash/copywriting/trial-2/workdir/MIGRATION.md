# Zrb API v2 Migration Guide

This guide covers every breaking change between Zrb Task API v1 and v2. It is intended for developers maintaining existing v1 integrations. Each change is presented with before/after examples so you can update your code confidently.

---

## Table of Contents

- [1. Endpoint Path Prefix — `/v2/`](#1-endpoint-path-prefix---v2)
- [2. Authentication Header — Bearer Token](#2-authentication-header---bearer-token)
- [3. Task ID — Integer to UUID](#3-task-id--integer-to-uuid)
- [4. Task Field — `done` Renamed to `completed`](#4-task-field--done-renamed-to-completed)
- [5. Task Creation — `project_id` Now Required](#5-task-creation--project_id-now-required)
- [6. List Responses — Paginated Envelope](#6-list-responses--paginated-envelope)
- [Step-by-Step Migration Checklist](#step-by-step-migration-checklist)
- [Upgrade Command](#upgrade-command)

---

## 1. Endpoint Path Prefix — `/v2/`

All endpoints are now prefixed with `/v2/`. Requests to v1 paths will **not** be forwarded or aliased.

**Before (v1):**

```
GET /tasks
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2):**

```
GET /v2/tasks
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

**Action:** Update all base URLs or path builders in your client to prepend `/v2` to every endpoint.

---

## 2. Authentication Header — Bearer Token

The custom `X-Auth-Token` header has been replaced with a standard Bearer token via the `Authorization` header. Requests using the old header will receive **HTTP 401 Unauthorized**.

**Before (v1):**

```
X-Auth-Token: your_api_key
```

**After (v2):**

```
Authorization: Bearer your_api_token
```

**Action:** Replace the header name and value format. Generate a new API token from the Zrb dashboard if you haven't already — your old API key will not work.

---

## 3. Task ID — Integer to UUID

Task `id` values are now UUID strings (v4) instead of auto-incrementing integers. This affects how you reference tasks across all endpoints and how you store/compare IDs locally.

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

**Action:**
- Update any code that asserts `typeof id === 'number'` or reads `id` as an int.
- Change database columns or in-memory schemas from integer to UUID/string.
- Remove any logic that relied on sequential IDs (e.g., range queries, ID-based sorting).

---

## 4. Task Field — `done` Renamed to `completed`

The boolean field that tracks task completion has been renamed from `done` to `completed`. The semantics are identical — only the key changed.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Ship v2",
  "done": true
}
```

```http
PUT /tasks/42
Content-Type: application/json

{ "done": true }
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-...",
  "title": "Ship v2",
  "completed": true
}
```

```http
PUT /v2/tasks/a1b2c3d4-...
Content-Type: application/json

{ "completed": true }
```

**Action:** Rename all references to `done` to `completed` in request bodies, response parsing, and local data models. The old field is silently dropped — the API will not reject a `done` key, but it will be ignored.

---

## 5. Task Creation — `project_id` Now Required

Creating a task now requires a `project_id` field. Omitting it returns **HTTP 422 Unprocessable Entity**.

**Before (v1):**

```http
POST /tasks
Content-Type: application/json

{ "title": "Write tests" }
```

**After (v2):**

```http
POST /v2/tasks
Content-Type: application/json

{ "title": "Write tests", "project_id": "proj_abc123" }
```

**Action:**
- Obtain a valid `project_id` from the Zrb dashboard or the `GET /v2/projects` endpoint.
- Add `project_id` to every task creation call.
- Decide on a fallback (e.g., a default "Inbox" project) for any existing one-click task creation flows in your UI.

---

## 6. List Responses — Paginated Envelope

List endpoints no longer return a bare array. They return a paginated envelope with `items`, `total`, and `next_cursor`. Use the cursor to navigate pages.

**Before (v1):**

```http
GET /tasks
```

```json
[
  { "id": 1, "title": "Buy milk", "done": false },
  { "id": 2, "title": "Ship v1", "done": true }
]
```

**After (v2):**

```http
GET /v2/tasks?limit=20
```

```json
{
  "items": [
    { "id": "a1b2...", "title": "Buy milk", "completed": false },
    { "id": "c3d4...", "title": "Ship v1", "completed": true }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Fetching the next page (v2):**

```http
GET /v2/tasks?cursor=cursor_xyz&limit=20
```

**Action:**
- Access the task array via `response.items` instead of reading `response` directly.
- Use `response.next_cursor` to detect and fetch additional pages. An absent or `null` cursor means the last page.
- Optionally pass `?limit=` to control page size (default: 20, maximum: 100).

**Pattern (pseudocode):**

```python
def fetch_all_tasks():
    tasks = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = get("/v2/tasks", params=params)
        tasks.extend(resp["items"])
        if not resp.get("next_cursor"):
            break
        cursor = resp["next_cursor"]
    return tasks
```

---

## Step-by-Step Migration Checklist

1. **Generate a v2 API token** from the Zrb dashboard.
2. **Update the auth header** — change `X-Auth-Token` to `Authorization: Bearer <token>`.
3. **Prepend `/v2`** to every endpoint path in your client.
4. **Update task ID handling** — change all ID fields, columns, and parameters from integer to UUID/string.
5. **Rename `done` to `completed`** — in request bodies, response parsing, and local state.
6. **Add `project_id`** to all `POST /v2/tasks` calls. Validate that creation works for at least one project.
7. **Update list response parsing** — read `response.items` instead of the top-level array, and add cursor-based pagination.
8. **Verify against v2 sandbox** — run your integration tests against the v2 staging environment before deploying to production.

---

## Upgrade Command

Update your client dependency to use Zrb API v2:

```bash
pip install zrb-client>=2.0.0
```

Or, if you are using the HTTP API directly, update your base URL and activate the new token:

```bash
export ZRB_API_URL="https://api.zrb.dev/v2"
export ZRB_API_TOKEN="your_v2_token_here"
```
