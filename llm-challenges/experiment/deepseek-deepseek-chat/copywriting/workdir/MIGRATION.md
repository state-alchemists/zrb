# Zrb CLI v2 Migration Guide

Zrb v2 introduces projects, cursor-based pagination, and stricter authentication. All six changes below are **breaking** — existing v1 clients will not work against a v2 server without modification.

## Breaking Changes at a Glance

| # | Area | v1 | v2 |
|---|------|----|----|
| 1 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 2 | Authentication | `X-Auth-Token` header | `Authorization: Bearer` header |
| 3 | Task ID type | Integer (e.g., `42`) | UUID string (e.g., `"a1b2c3d4-..."`) |
| 4 | Completion field | `done` (boolean) | `completed` (boolean) |
| 5 | Task creation | `title` only | `title` + `project_id` (required) |
| 6 | List response | Bare array | Paginated envelope (`{items, total, next_cursor}`) |

---

## 1. Endpoint Prefix: `/v2/`

All resource paths are now prefixed with `/v2`. Requests to `/tasks` will **not** be forwarded.

**v1:**

```http
GET /tasks
POST /tasks
GET /tasks/42
PUT /tasks/42
DELETE /tasks/42
```

**v2:**

```http
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication Header

The old `X-Auth-Token` header has been replaced with a standard Bearer token. v2 **rejects** requests using the v1 header with HTTP 401.

**v1:**

```
X-Auth-Token: <your_api_key>
```

**v2:**

```
Authorization: Bearer <your_api_token>
```

If you previously stored the token as a plain API key, you will need to migrate to a Bearer token credential. Check your dashboard or contact your admin to generate one.

---

## 3. Task ID: Integer → UUID String

Task identifiers are now UUID v4 strings instead of auto-incrementing integers. This affects all endpoints that reference a task by ID (`GET`, `PUT`, `DELETE`) and all stored references to task IDs in your application.

**v1** response:

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**v2** response:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Migration steps by caller type:**

- **Database**: If you cached task IDs locally, alter the column type from `INTEGER` / `SERIAL` to `UUID`. Existing integer IDs will be reassigned during migration — plan for a mapping phase.
- **URL construction**: Change `tasks/${id}` to accept string IDs instead of integers.
- **Comparison logic**: Any `===` or `==` against task IDs must handle strings.

---

## 4. Field Renamed: `done` → `completed`

The boolean field indicating task completion has been renamed from `done` to `completed`.

**v1** read and write:

```json
{ "done": true }
```

**v2** read and write:

```json
{ "completed": true }
```

**Effect:**

- **Incoming data**: Code that reads `task.done` will receive `undefined` / `null`. Every consumer must read `task.completed` instead.
- **Outgoing data**: `PUT /v2/tasks/{id}` with `{ "done": true }` will silently ignore the unknown field (no error). Use `{ "completed": true }` instead.
- **Schema validation**: If you validate responses or request bodies against a schema, update the field name.

---

## 5. `project_id` Required on Create

Task creation now requires a `project_id` field. Omitting it returns HTTP 422 Unprocessable Entity.

**v1** create request:

```json
POST /tasks
{
  "title": "New task title"
}
```

**v2** create request:

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

If you maintain a list of projects separately, obtain the `project_id` before creating tasks. The server assigns tasks to projects; there is no default fallback.

---

## 6. Paginated Response Envelope

List endpoints no longer return a bare array. All collection responses are wrapped in a paginated envelope with cursor-based pagination.

**v1** list response (bare array):

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**v2** list response (paginated envelope):

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "e5f6a7b8-...", "title": "Ship v1", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Effect:**

- Access the array via `response.items` instead of `response` directly.
- To fetch the next page, pass `?cursor=<next_cursor>` on the next request. A `null` / absent `next_cursor` means you've reached the last page.
- The `limit` query parameter controls page size (default: 20).

---

## Migration Checklist

Use this checklist to track your progress. Each item references the section above.

- [ ] **Update endpoint prefixes**: Replace all `/tasks` with `/v2/tasks`.
- [ ] **Switch auth header**: Replace `X-Auth-Token` with `Authorization: Bearer` and obtain a Bearer token.
- [ ] **Migrate task IDs**: Update database schemas, URL construction, and comparison logic to handle UUID strings.
- [ ] **Rename `done` → `completed`**: Update all JSON read/write paths and schema validators.
- [ ] **Add `project_id`**: Ensure every `POST /v2/tasks` call includes a valid `project_id`.
- [ ] **Unwrap paginated responses**: Access list data through `response.items`, and implement cursor-based pagination where you fetch multiple pages.
- [ ] **Update client library / SDK** (if applicable): Bump any generated or hand-rolled API client.
- [ ] **Run integration tests**: Verify every CRUD operation against a v2 staging environment before deploying to production.

---

## Upgrade Command

Once your code is updated, bump your dependency:

```bash
zrb upgrade --to v2
```

Or, for a clean install:

```bash
pip install zrb>=2.0.0
```
