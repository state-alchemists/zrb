# Zrb Task API v1 → v2 Migration Guide

This guide covers all breaking changes when migrating clients from the v1 Zrb Task API to v2. It assumes you already have a working v1 integration.

## TL;DR (what will break)

v2 is not wire-compatible with v1. You must update:
- Base paths (all endpoints move under `/v2/`)
- Authentication header (Bearer token)
- Task identifiers (integer → UUID string)
- Task schema (`done` → `completed`, plus required `project_id`)
- List responses (bare array → paginated envelope)

---

## 1) Breaking change: all endpoints are now prefixed with `/v2/`

In v1, endpoints lived at `/tasks`, `/tasks/{id}`, etc. In v2, every endpoint is namespaced under `/v2/`.

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
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
POST /v2/tasks
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

If you hard-coded URLs, change them. If you have a shared API client, prefer a single configurable base path (e.g., `baseUrl + "/v2"`).

---

## 2) Breaking change: authentication header changed (and v1 header now 401s)

v1 uses an API key header:

Before (v1):
```http
X-Auth-Token: <your_api_key>
```

v2 requires a Bearer token:

After (v2):
```http
Authorization: Bearer <your_api_token>
```

Requests that still send `X-Auth-Token` will receive HTTP 401 in v2.

Example (curl)

Before (v1):
```bash
curl -sS https://api.example.com/tasks \
  -H 'X-Auth-Token: YOUR_API_KEY'
```

After (v2):
```bash
curl -sS https://api.example.com/v2/tasks \
  -H 'Authorization: Bearer YOUR_API_TOKEN'
```

---

## 3) Breaking change: Task `id` changed from integer to UUID string

In v1, task IDs are integers (e.g., `42`). In v2, task IDs are UUID strings.

Before (v1 Task):
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

After (v2 Task):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

What to change in your code:
- Treat `id` as an opaque string (do not parse as int; do not assume ordering).
- Update route builders and storage types.

Example (TypeScript)

Before (v1):
```ts
type TaskV1 = {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
};

function taskUrl(baseUrl: string, id: number) {
  return `${baseUrl}/tasks/${id}`;
}
```

After (v2):
```ts
type TaskV2 = {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
};

function taskUrl(baseUrl: string, id: string) {
  return `${baseUrl}/v2/tasks/${id}`;
}
```

---

## 4) Breaking change: Task field `done` renamed to `completed`

The boolean status field is renamed.

Before (v1 update request):
```json
{
  "title": "Updated title",
  "done": true
}
```

After (v2 update request):
```json
{
  "title": "Updated title",
  "completed": true
}
```

Example (Python)

Before (v1):
```py
payload = {"done": True}
requests.put(f"{base_url}/tasks/{task_id}", json=payload, headers=headers)
```

After (v2):
```py
payload = {"completed": True}
requests.put(f"{base_url}/v2/tasks/{task_id}", json=payload, headers=headers)
```

---

## 5) Breaking change: creating a task now requires `project_id`

In v1, creating a task only required `title`. In v2, `project_id` is required.

Omitting `project_id` returns HTTP 422.

Before (v1 create request):
```json
{
  "title": "New task title"
}
```

After (v2 create request):
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

Example (curl)

Before (v1):
```bash
curl -sS -X POST https://api.example.com/tasks \
  -H 'X-Auth-Token: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title"}'
```

After (v2):
```bash
curl -sS -X POST https://api.example.com/v2/tasks \
  -H 'Authorization: Bearer YOUR_API_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"title":"New task title","project_id":"proj_abc123"}'
```

---

## 6) Breaking change: list endpoints are now paginated (envelope response)

In v1, `GET /tasks` returns a bare array.

Before (v1 list response):
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

In v2, `GET /v2/tasks` returns an envelope with `items`, `total`, and `next_cursor`.

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

To fetch the next page, pass `?cursor=<next_cursor>` (and optionally `limit`).

Example (JavaScript pagination loop)

Before (v1):
```js
const res = await fetch(`${baseUrl}/tasks`, { headers });
const tasks = await res.json(); // tasks is an array
for (const t of tasks) {
  console.log(t.id, t.done);
}
```

After (v2):
```js
let cursor = undefined;

while (true) {
  const url = new URL(`${baseUrl}/v2/tasks`);
  if (cursor) url.searchParams.set("cursor", cursor);
  url.searchParams.set("limit", "20");

  const res = await fetch(url, { headers });
  const page = await res.json(); // { items, total, next_cursor }

  for (const t of page.items) {
    console.log(t.id, t.completed);
  }

  if (!page.next_cursor) break;
  cursor = page.next_cursor;
}
```

---

## Migration checklist (step-by-step)

1. Update your API base paths to use `/v2/` (e.g., `/tasks` → `/v2/tasks`).
2. Replace `X-Auth-Token` auth with `Authorization: Bearer <token>`.
3. Update all Task ID handling:
   - Change types from integer/number to string.
   - Treat IDs as opaque UUIDs.
4. Rename all request/response handling of `done` → `completed`.
5. Update task creation flows to always provide `project_id`.
   - If your app didn’t have projects, decide how you will source/store a `project_id`.
6. Update list parsing and iteration:
   - Expect `{ items, total, next_cursor }`.
   - Implement cursor pagination using `?cursor=` (and optionally `limit`).
7. Run your integration test suite against v2 endpoints and verify:
   - Authentication works (no 401s).
   - Create returns 201 with `project_id` present.
   - Update toggles `completed` correctly.
   - List traverses multiple pages correctly.

---

## Upgrade

```bash
zrb upgrade --major v2
```
