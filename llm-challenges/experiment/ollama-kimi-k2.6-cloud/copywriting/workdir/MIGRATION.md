# Zrb CLI v1 to v2 Migration Guide

Zrb v2 introduces projects, cursor-based pagination, and stricter authentication. This guide covers every breaking change you need to address before your existing v1 integration will work with v2.

If you are already running v1 in production, migrate in three phases: update requests locally, verify against the v2 endpoints, and then upgrade your CLI.

---

## 1. Endpoint Prefix

**Breaking change:** All endpoints are now prefixed with `/v2/`.

Requests to the old unversioned paths will fail.

### Before (v1)

```bash
curl -H "X-Auth-Token: <token>" \
  https://api.zrb.dev/tasks
```

### After (v2)

```bash
curl -H "Authorization: Bearer <token>" \
  https://api.zrb.dev/v2/tasks
```

---

## 2. Authentication Header

**Breaking change:** The `X-Auth-Token` header is removed. You must send a Bearer token in the `Authorization` header. v2 returns `401 Unauthorized` for the old header.

### Before (v1)

```bash
curl -H "X-Auth-Token: my-api-key" \
  https://api.zrb.dev/tasks
```

```python
import requests

headers = {"X-Auth-Token": "my-api-key"}
response = requests.get("https://api.zrb.dev/tasks", headers=headers)
```

### After (v2)

```bash
curl -H "Authorization: Bearer my-api-token" \
  https://api.zrb.dev/v2/tasks
```

```python
import requests

headers = {"Authorization": "Bearer my-api-token"}
response = requests.get("https://api.zrb.dev/v2/tasks", headers=headers)
```

---

## 3. Task ID Type

**Breaking change:** `id` is now a UUID string instead of an integer. Update any client-side code that assumes numeric IDs or performs integer math on task identifiers.

### Before (v1)

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
const taskId = 42;
const url = `https://api.zrb.dev/tasks/${taskId}`;
```

### After (v2)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

```javascript
const taskId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
const url = `https://api.zrb.dev/v2/tasks/${taskId}`;
```

---

## 4. Field Rename: `done` → `completed`

**Breaking change:** The boolean field `done` is renamed to `completed`. Requests that send `done` in the v2 API will be ignored, and responses no longer contain the old key.

### Before (v1)

```json
{
  "title": "Updated title",
  "done": true
}
```

```python
task = {"title": "Updated title", "done": True}
requests.put(f"https://api.zrb.dev/tasks/{task_id}", json=task)
```

### After (v2)

```json
{
  "title": "Updated title",
  "completed": true
}
```

```python
task = {"title": "Updated title", "completed": True}
requests.put(f"https://api.zrb.dev/v2/tasks/{task_id}", json=task)
```

---

## 5. Required `project_id` on Task Creation

**Breaking change:** Creating a task now requires a `project_id`. Omitting it returns `422 Unprocessable Entity`.

### Before (v1)

```json
{
  "title": "New task title"
}
```

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: <token>" \
  -d '{"title": "New task title"}'
```

### After (v2)

```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title": "New task title", "project_id": "proj_abc123"}'
```

---

## 6. Paginated List Response

**Breaking change:** `GET /tasks` no longer returns a bare array. It returns a paginated envelope with `items`, `total`, and `next_cursor`.

Cursor pagination replaces offset pagination. Pass `?cursor=<next_cursor>` to fetch the next page.

### Before (v1)

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

```javascript
const tasks = await response.json();
for (const task of tasks) {
  console.log(task.title);
}
```

### After (v2)

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "b2c3d4e5-...", "title": "Ship v1", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```javascript
const body = await response.json();
for (const task of body.items) {
  console.log(task.title);
}

if (body.next_cursor) {
  const nextPage = await fetch(`/v2/tasks?cursor=${body.next_cursor}`);
}
```

---

## Migration Checklist

Use this checklist to verify you have updated every integration point before switching your production traffic to v2.

- [ ] Update every request URL to include the `/v2/` prefix.
- [ ] Replace `X-Auth-Token: <key>` with `Authorization: Bearer <token>` in all HTTP clients.
- [ ] Verify your token format matches the new Bearer scheme (v2 tokens may differ from v1 API keys).
- [ ] Change client-side types so `task.id` is treated as a UUID string, not an integer.
- [ ] Rename every reference from `task.done` to `task.completed` in request bodies and response parsing.
- [ ] Add `project_id` to all task creation payloads.
- [ ] Update list-task consumers to read `response.items` instead of the root array.
- [ ] Implement cursor pagination if you currently iterate over more than one page of results.
- [ ] Run your test suite against the v2 endpoints in a staging environment.
- [ ] Update internal documentation and client SDKs to reference the new fields and paths.

---

## Upgrade Command

Once your code is compatible with the changes above, upgrade the CLI to v2:

```bash
npm install -g zrb-cli@latest
```

After installation, confirm the version:

```bash
zrb --version
```

If you have questions or hit an edge case not covered here, open a discussion in the [Zrb community forum](https://github.com/zrb-dev/zrb/discussions).
