# Zrb CLI / Task API v1 → v2 Migration Guide

This guide helps existing v1 integrators migrate to v2. v2 introduces projects, cursor-based pagination, and stricter authentication. All changes below are breaking relative to v1.

## At a glance (breaking changes)

1) Base path: endpoints are now prefixed with `/v2/`
2) Auth: `X-Auth-Token` header replaced by `Authorization: Bearer …`
3) Identifiers: task `id` changed from integer to UUID string
4) Field rename: task `done` renamed to `completed`
5) Create semantics: `project_id` is now required when creating tasks
6) Responses: list endpoints return a paginated envelope (not a bare array)

---

## 1) Base path changed: `/tasks` → `/v2/tasks`

In v1, endpoints were unversioned (e.g. `/tasks`). In v2, every endpoint is under `/v2/`.

Before (v1):
```http
GET /tasks
GET /tasks/42
POST /tasks
PUT /tasks/42
DELETE /tasks/42
```

After (v2):
```http
GET /v2/tasks
GET /v2/tasks/{id}
POST /v2/tasks
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

If you have a shared base URL constant, update it once rather than changing call sites.

---

## 2) Authentication header changed

v1 used an API key in `X-Auth-Token`. v2 requires a Bearer token in the `Authorization` header. Requests using `X-Auth-Token` will receive HTTP 401 in v2.

Before (v1):
```bash
curl -s \
  -H 'X-Auth-Token: <your_api_key>' \
  https://api.example.com/tasks
```

After (v2):
```bash
curl -s \
  -H 'Authorization: Bearer <your_api_token>' \
  https://api.example.com/v2/tasks
```

---

## 3) Task `id` type changed: integer → UUID string

In v1, task IDs were integers (e.g. `42`). In v2, IDs are UUID strings (e.g. `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

Impact:
- Update any code assuming numeric IDs (parsing, validation, database schema, URL builders).
- If you used `int` types in strongly-typed clients, change them to `string` (or a UUID type).

Before (v1):
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

After (v2):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Before (v1 URL construction):
```js
const id = 42;
const url = `${baseUrl}/tasks/${id}`;
```

After (v2 URL construction):
```js
const id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
const url = `${baseUrl}/v2/tasks/${id}`;
```

---

## 4) Task field renamed: `done` → `completed`

v1 task objects used `done`. v2 renames this to `completed`.

Impact:
- Update serializers/deserializers.
- Update any filtering logic (e.g. “show done tasks”).
- Update update requests: `done` is no longer accepted; use `completed`.

Before (v1 update request):
```bash
curl -s -X PUT \
  -H 'X-Auth-Token: <your_api_key>' \
  -H 'Content-Type: application/json' \
  -d '{"done": true}' \
  https://api.example.com/tasks/42
```

After (v2 update request):
```bash
curl -s -X PUT \
  -H 'Authorization: Bearer <your_api_token>' \
  -H 'Content-Type: application/json' \
  -d '{"completed": true}' \
  https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Before (v1 model/type):
```ts
type TaskV1 = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};
```

After (v2 model/type):
```ts
type TaskV2 = {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
};
```

---

## 5) Create Task now requires `project_id`

In v1, creating a task required only `title`. In v2, `project_id` is required and omitting it returns HTTP 422.

Before (v1 create request):
```bash
curl -s -X POST \
  -H 'X-Auth-Token: <your_api_key>' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title"}' \
  https://api.example.com/tasks
```

After (v2 create request):
```bash
curl -s -X POST \
  -H 'Authorization: Bearer <your_api_token>' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title","project_id":"proj_abc123"}' \
  https://api.example.com/v2/tasks
```

If your app previously created tasks without any project context, you must decide how to source `project_id` (e.g. a default project per workspace/user) before upgrading.

---

## 6) List endpoints are now paginated (envelope response)

In v1, `GET /tasks` returned a bare JSON array. In v2, `GET /v2/tasks` returns an envelope with `items`, `total`, and `next_cursor`. Fetch subsequent pages with `?cursor=<next_cursor>`.

Before (v1 response):
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

After (v2 response):
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

Before (v1 client parsing):
```js
const res = await fetch(`${baseUrl}/tasks`, { headers });
const tasks = await res.json(); // tasks is an array
for (const t of tasks) console.log(t.title);
```

After (v2 client parsing + pagination):
```js
async function listAllTasks() {
  const tasks = [];
  let cursor;

  while (true) {
    const url = new URL(`${baseUrl}/v2/tasks`);
    if (cursor) url.searchParams.set('cursor', cursor);

    const res = await fetch(url, { headers });
    const page = await res.json(); // { items, total, next_cursor }

    tasks.push(...page.items);
    if (!page.next_cursor) break;
    cursor = page.next_cursor;
  }

  return tasks;
}
```

---

## Step-by-step migration checklist

1. Update your API base path to include `/v2/` for all task endpoints.
2. Replace `X-Auth-Token` with `Authorization: Bearer <token>` everywhere.
3. Update task ID handling:
   - Treat `id` as a string/UUID (not an integer).
   - Update validation/parsing and any typed client models.
4. Rename all usages of `done` to `completed`:
   - Response parsing
   - Update requests (`PUT` payloads)
   - Any business logic based on completion state
5. Update task creation to include `project_id` and handle HTTP 422 for missing/invalid input.
6. Update list-task callers to handle the paginated envelope:
   - Parse `items` instead of a top-level array
   - Implement cursor pagination using `next_cursor`
   - Consider `limit` tuning (default 20)
7. Verify end-to-end:
   - Create a task (with `project_id`)
   - List tasks (multiple pages if applicable)
   - Update completion state via `completed`
   - Fetch by id (UUID)
   - Delete a task

## Upgrade command

```bash
zrb upgrade --major v2
```
