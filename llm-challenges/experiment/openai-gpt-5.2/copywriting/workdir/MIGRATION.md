# Zrb Task API v1 → v2 Migration Guide

This guide covers **all breaking changes** between the Zrb Task API v1 and v2 and shows how to update existing integrations.

## Quick mapping

| Area | v1 | v2 |
|---|---|---|
| Base path | `/` | `/v2/` |
| Auth header | `X-Auth-Token: <key>` | `Authorization: Bearer <token>` |
| Task id | integer (`42`) | UUID string (`"a1b2…"`) |
| Completion field | `done` | `completed` |
| Create task required fields | `title` | `title` + `project_id` |
| List response shape | bare array | paginated envelope `{ items, total, next_cursor }` |

---

## 1) Breaking change: all endpoints are now prefixed with `/v2/`

**What changed**

Every endpoint moved from (for example) `GET /tasks` to `GET /v2/tasks`.

**Before (v1)**

```http
GET /tasks
```

```http
POST /tasks
Content-Type: application/json

{"title":"New task title"}
```

**After (v2)**

```http
GET /v2/tasks
```

```http
POST /v2/tasks
Content-Type: application/json

{"title":"New task title","project_id":"proj_abc123"}
```

---

## 2) Breaking change: authentication header changed (API key → Bearer token)

**What changed**

- v1 used `X-Auth-Token: <your_api_key>`.
- v2 requires `Authorization: Bearer <your_api_token>`.
- Requests that still send `X-Auth-Token` will receive **HTTP 401**.

**Before (v1)**

```bash
curl -sS \
  -H 'X-Auth-Token: YOUR_API_KEY' \
  https://api.example.com/tasks
```

**After (v2)**

```bash
curl -sS \
  -H 'Authorization: Bearer YOUR_API_TOKEN' \
  https://api.example.com/v2/tasks
```

---

## 3) Breaking change: Task `id` changed from integer to UUID string

**What changed**

- v1 task IDs were integers (e.g. `42`).
- v2 task IDs are UUID strings (e.g. `"a1b2c3d4-e5f6-..."`).

This affects:
- URL construction (`/tasks/{id}`)
- database schemas/types in your client
- parsing/validation logic

**Before (v1)**

```http
GET /tasks/42
```

```json
{"id":42,"title":"Write tests","done":false,"created_at":"2024-01-15T10:30:00Z"}
```

**After (v2)**

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

```json
{"id":"a1b2c3d4-e5f6-7890-abcd-ef1234567890","title":"Write tests","completed":false,"project_id":"proj_abc123","created_at":"2024-01-15T10:30:00Z"}
```

---

## 4) Breaking change: Task field `done` renamed to `completed`

**What changed**

- v1: `done` (boolean)
- v2: `completed` (boolean)

You must update:
- serializers/deserializers
- query filters
- update payloads

**Before (v1)**

```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2)**

```json
{
  "title": "Updated title",
  "completed": true
}
```

---

## 5) Breaking change: creating a task now requires `project_id`

**What changed**

- v1 create required only `title`.
- v2 create requires **both** `title` and `project_id`.
- Omitting `project_id` returns **HTTP 422**.

**Before (v1)**

```http
POST /tasks
Content-Type: application/json

{"title":"New task title"}
```

**After (v2)**

```http
POST /v2/tasks
Content-Type: application/json

{"title":"New task title","project_id":"proj_abc123"}
```

---

## 6) Breaking change: list endpoints return a paginated envelope (not a bare array)

**What changed**

- v1 `GET /tasks` returned a JSON array.
- v2 `GET /v2/tasks` returns an object envelope:
  - `items`: array of tasks
  - `total`: total available tasks
  - `next_cursor`: cursor for the next page (or possibly `null`/missing when done)

v2 also adds query params:
- `limit` (default 20)
- `cursor` (use the `next_cursor` from the previous response)

**Before (v1)**

```http
GET /tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2)**

```http
GET /v2/tasks?limit=20
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

### Example: cursor-based pagination loop

**Before (v1): single request**

```js
// v1: one request gets all tasks
const res = await fetch(`${baseUrl}/tasks`, {
  headers: { 'X-Auth-Token': apiKey },
});
const tasks = await res.json(); // Array
```

**After (v2): iterate until `next_cursor` is empty**

```js
let cursor = undefined;
const all = [];

while (true) {
  const url = new URL(`${baseUrl}/v2/tasks`);
  url.searchParams.set('limit', '20');
  if (cursor) url.searchParams.set('cursor', cursor);

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${apiToken}` },
  });

  const page = await res.json(); // { items, total, next_cursor }
  all.push(...page.items);

  if (!page.next_cursor) break;
  cursor = page.next_cursor;
}
```

---

## Migration checklist (step-by-step)

1. **Update base URLs**: change all endpoint paths from `/…` to `/v2/…`.
2. **Switch authentication**:
   - Remove `X-Auth-Token`.
   - Send `Authorization: Bearer <token>`.
   - Ensure your config/secret management uses the new token value.
3. **Update task ID handling**:
   - Change types from integer to string/UUID in your client models.
   - Update any validation and storage schemas.
4. **Rename completion field**:
   - Replace `done` with `completed` in request payloads and response parsing.
5. **Update create-task calls**:
   - Ensure `project_id` is provided for every task creation.
   - Handle HTTP 422 as a validation error.
6. **Fix list-task consumers**:
   - Update parsers from `Task[]` to `{ items: Task[], total: number, next_cursor: string }`.
   - Implement cursor-based pagination where you previously assumed a single page.
7. **Regression test key flows**:
   - List tasks, create task, update completion, fetch by id, delete.

---

## Upgrade command

```bash
zrb upgrade --major v2
```
