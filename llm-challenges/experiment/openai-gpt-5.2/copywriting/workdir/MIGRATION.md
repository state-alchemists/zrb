# Zrb CLI / Task API v1 → v2 Migration Guide

This guide is for developers already integrated with Zrb v1 who need to upgrade to v2. v2 introduces projects, cursor-based pagination, stricter authentication, and several incompatible API and data model changes.

## TL;DR

- All routes move under `/v2/`.
- `X-Auth-Token` is replaced by `Authorization: Bearer ...`.
- Task identifiers change from integer to UUID string.
- Task field `done` is renamed to `completed`.
- Creating a task now requires `project_id`.
- List endpoints are now paginated and return an envelope (`items`, `total`, `next_cursor`).

## Prerequisites

- You have a v2 API token (Bearer token).
- You know which `project_id` to create tasks under.

If you previously stored numeric task IDs or assumed list endpoints return a plain array, you must update those assumptions.

---

## Breaking change 1: Base path is now `/v2/`

In v1, endpoints were unversioned (e.g., `GET /tasks`). In v2, every endpoint is prefixed with `/v2/` (e.g., `GET /v2/tasks`).

Before (v1):
```bash
curl -sS \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  https://api.example.com/tasks
```

After (v2):
```bash
curl -sS \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  https://api.example.com/v2/tasks
```

What to change:
- Update your API client base URL (or route builder) to include `/v2`.
- Avoid concatenating `"/tasks"` directly to a previously versionless base URL.

---

## Breaking change 2: Authentication header changed to Bearer token

v1 used an API key in `X-Auth-Token`. v2 requires a Bearer token in the standard `Authorization` header. Requests using `X-Auth-Token` will receive HTTP 401.

Before (v1):
```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
```

After (v2):
```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
```

What to change:
- Replace header name and value format.
- If you used middleware/interceptors that inject `X-Auth-Token`, update them.

---

## Breaking change 3: Task `id` changed from integer to UUID string

v1 task IDs were integers (e.g., `42`). v2 task IDs are UUID strings (e.g., `"a1b2..."`). This affects URL construction, persistence, validation, and database schema if you store task IDs.

Before (v1 task object):
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

After (v2 task object):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Before (v1 get/update URL):
```bash
curl -sS \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  https://api.example.com/tasks/42
```

After (v2 get/update URL):
```bash
curl -sS \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

What to change:
- Treat IDs as opaque strings, not numbers.
- Remove integer parsing/casting and numeric validation.
- Update any DB columns or types that assumed integer IDs.

---

## Breaking change 4: Task field `done` renamed to `completed`

In v1, the completion flag was `done`. In v2, it is `completed`.

Before (v1 update):
```bash
curl -sS -X PUT \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"done": true}' \
  https://api.example.com/tasks/42
```

After (v2 update):
```bash
curl -sS -X PUT \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"completed": true}' \
  https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

What to change:
- Update serializers/deserializers and any mapping logic.
- Update UI/state code that reads/writes `done`.

---

## Breaking change 5: Creating a task now requires `project_id`

In v1, you could create a task with just a `title`. In v2, `project_id` is required. Omitting it returns HTTP 422.

Before (v1 create):
```bash
curl -sS -X POST \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title"}' \
  https://api.example.com/tasks
```

After (v2 create):
```bash
curl -sS -X POST \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title","project_id":"proj_abc123"}' \
  https://api.example.com/v2/tasks
```

What to change:
- Ensure your application knows the target `project_id` at creation time.
- Update any server-side validation expectations and client-side forms.

---

## Breaking change 6: List endpoints are now paginated (envelope response)

In v1, `GET /tasks` returned a bare JSON array. In v2, `GET /v2/tasks` returns a paginated envelope with `items`, `total`, and `next_cursor`. Fetch subsequent pages with `?cursor=<next_cursor>`.

Before (v1 list response):
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

After (v2 list response):
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

Before (v1 list call):
```bash
curl -sS \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  https://api.example.com/tasks
```

After (v2 list call with pagination):
```bash
# first page
curl -sS \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  "https://api.example.com/v2/tasks?limit=20"

# next page (if next_cursor is not null)
curl -sS \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  "https://api.example.com/v2/tasks?cursor=cursor_xyz&limit=20"
```

What to change:
- Update code that assumes the response is an array; it must read `response.items`.
- Implement cursor iteration if you need the full list.
- Consider whether your use case can stay paged (often faster and safer).

---

## Step-by-step migration checklist

1. Inventory v1 usages
   - Search for `/tasks` routes and v1 base URLs.
   - Search for `X-Auth-Token` usage.
   - Search for JSON field `done`.
   - Search for any code that parses task IDs as integers.

2. Update routing to v2
   - Change all endpoint paths to start with `/v2/`.

3. Update authentication
   - Replace `X-Auth-Token: <key>` with `Authorization: Bearer <token>`.
   - Rotate/configure secrets so v2 tokens are available in all environments.

4. Update models and storage
   - Change task ID type from integer to string/UUID.
   - Rename `done` → `completed` in DTOs, schemas, and UI state.
   - Add `project_id` to task model where relevant.

5. Update create-task flows
   - Ensure `project_id` is available at task creation.
   - Add validation to prevent sending creates without `project_id` (avoid HTTP 422).

6. Update list-task handling
   - Parse list responses from `{ items, total, next_cursor }`.
   - Implement cursor pagination where needed.
   - Verify `limit` usage (default is 20).

7. Verify end-to-end behavior
   - Create a task (ensure `project_id` is set).
   - List tasks (ensure you read `items`).
   - Update a task (ensure `completed` is used).
   - Get/delete by UUID.

8. Remove v1 compatibility code (optional but recommended)
   - Delete legacy parsing/mapping layers once v2 is deployed everywhere.

## Upgrade command

```bash
zrb upgrade --major v2
```
