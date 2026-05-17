# Zrb API Migration Guide: v1 → v2

For experienced developers upgrading from Zrb v1 to v2.

This guide describes all breaking changes and provides concrete code examples for successful migration.

---

## Breaking Changes Overview

| # | Change | Impact | Severity |
|---|--------|--------|----------|
| 1 | Endpoint base path changed to `/v2/` | All requests must use new paths | High |
| 2 | Authentication header changed to `Authorization: Bearer` | Existing requests fail with 401 | Critical |
| 3 | Task `id` type changed from integer to UUID string | Type mismatches if unchanged | High |
| 4 | Task field `done` → `completed` | serialization/deserialization failure | High |
| 5 | Task creation now requires `project_id` | Missing field returns 422 | High |
| 6 | List responses follow pagination envelope | Direct array access breaks | Medium |

---

## 1. Endpoint Path Changes

All API endpoints now begin with `/v2/`.

| v1 Endpoint | v2 Endpoint |
|-------------|-------------|
| `GET /tasks` | `GET /v2/tasks` |
| `POST /tasks` | `POST /v2/tasks` |
| `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

### Before (v1)
```bash
curl -H "X-Auth-Token: YOUR_API_KEY" \
  https://api.zrb.dev/tasks
```

### After (v2)
```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  https://api.zrb.dev/v2/tasks
```

---

## 2. Authentication Header

The authentication header changed from `X-Auth-Token` to Bearer token in `Authorization`.

- v1 header: `X-Auth-Token: <your_api_key>` → HTTP 401 in v2
- v2 header: `Authorization: Bearer <your_api_token>` → required for all requests

### Before (v1)
```javascript
const response = await fetch('https://api.zrb.dev/tasks', {
  headers: {
    'X-Auth-Token': process.env.ZRB_API_KEY,
    'Content-Type': 'application/json'
  }
});
```

### After (v2)
```javascript
const response = await fetch('https://api.zrb.dev/v2/tasks', {
  headers: {
    'Authorization': `Bearer ${process.env.ZRB_API_TOKEN}`,
    'Content-Type': 'application/json'
  }
});
```

---

## 3. Task ID Type: Integer → UUID String

Task `id` values are now UUID strings instead of integers.

### Before (v1)
```json
{ "id": 42, "title": "Ship v1", "done": true }
```

### After (v2)
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Ship v1", "completed": true }
```

**Impact:** Validation and string conversion may be required.

### Before (v1) — type mismatch
```typescript
interface Task {
  id: number; // integer
  title: string;
  done: boolean;
}
```

### After (v2)
```typescript
interface Task {
  id: string; // UUID string
  title: string;
  completed: boolean;
  project_id: string;
}
```

---

## 4. Task Field Renamed: `done` → `completed`

The boolean field `done` is now named `completed`.

### Before (v1)
```json
{ "id": 1, "title": "Buy milk", "done": false, "created_at": "..." }
```

### After (v2)
```json
{ "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "created_at": "...", "project_id": "proj_abc" }
```

### Before (v1)
```python
task = {"id": 1, "title": "Do laundry", "done": False}
print(task["done"])  # True/False
```

### After (v2)
```python
task = {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Do laundry", "completed": False, "project_id": "proj_xyz"}
print(task["completed"])  # True/False
```

---

## 5. Project ID Required for Task Creation

Creating tasks now requires a `project_id` field. Omitting it returns HTTP 422.

### Before (v1)
```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "Implement features"}'
```

### After (v2)
```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Implement features", "project_id": "proj_abc123"}'
```

### Before (v1)
```javascript
await api.post('/tasks', { title: 'Write docs' });
```

### After (v2)
```javascript
await api.post('/v2/tasks', { 
  title: 'Write docs',
  project_id: 'proj_abc123'
});
```

---

## 6. Paginated List Responses

List endpoints return a pagination envelope with `items`, `total`, and `next_cursor` instead of a bare array.

### Before (v1)
```json
[
  { "id": 1, "title": "Buy milk", "done": false },
  { "id": 2, "title": "Ship v1", "done": true }
]
```

### After (v2)
```json
{
  "items": [
    { "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_x", "created_at": "..." },
    { "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "title": "Ship v1", "completed": true, "project_id": "proj_y", "created_at": "..." }
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

### Before (v1) — fails in v2
```javascript
const response = await fetch('https://api.zrb.dev/v2/tasks');
const tasks = await response.json(); // This is now an object, not an array!
tasks.forEach(task => { /* will error: forEach is not a function */ });
```

### After (v2)
```javascript
const response = await fetch('https://api.zrb.dev/v2/tasks?limit=50');
const result = await response.json();
const tasks = result.items;

// Pagination: fetch next page
if (result.next_cursor) {
  const nextResponse = await fetch(`https://api.zrb.dev/v2/tasks?cursor=${result.next_cursor}`);
  const nextResult = await nextResponse.json();
  // ...
}
```

---

## Step-by-Step Migration Checklist

1. **Update API base URL**
   - Change all API endpoints to include `/v2/` prefix
   - Example: `/tasks` → `/v2/tasks`

2. **Update authentication**
   - Replace `X-Auth-Token` header with `Authorization: Bearer <token>`
   - Ensure new token has required scope (check v2 docs)

3. **Update task ID handling**
   - Change type expectations from `number` to `string`
   - Update validation logic (e.g., regex for UUID or use a UUID library)

4. **Rename `done` to `completed`**
   - Update all request bodies for create/update operations
   - Update all response parsing to read `completed` field
   - Update models/interfaces

5. **Add `project_id` to create requests**
   - Modify task creation code to include required `project_id`
   - Collect or generate project IDs before creating tasks

6. **Handle paginated responses**
   - Update list response processing to access `response.items`
   - Implement cursor-based pagination if needed
   - Update loop logic to iterate over `items`, not raw response

7. **Test endpoint-by-endpoint**
   - Test `/v2/tasks` (GET) → verify pagination envelope
   - Test `/v2/tasks` (POST) → verify required `project_id`
   - Test `/v2/tasks/{id}` → verify UUID format
   - Test updates → verify `completed` field name
   - Test auth → verify Bearer token works

8. **Update SDKs/wrappers**
   - Update any custom API wrapper classes
   - Update language-specific SDKs if provided

9. **Update client-side code**
   - Frontend frameworks: update API calls and type definitions
   - Mobile apps: update network layer and data models

10. **Monitor error codes**
    - watch for HTTP 401 (auth issue)
    - watch for HTTP 422 (missing project_id)
    - watch for type mismatches (UUID strings vs integers)

---

## Upgrade Command

After making the code changes above, install the updated Zrb SDK:

```bash
npm install @zrb/sdk@latest
```

or, if using the CLI tool:

```bash
npm install -g zrb-cli@latest
```

Then run the `zrb migrate:v1-to-v2` diagnostic command to verify your migration:

```bash
zrb migrate:v1-to-v2 --dry-run
```

To apply automatic fixes (where possible):

```bash
zrb migrate:v1-to-v2 --apply
```

---

## Need Help?

- Review the [v2 Full Reference](./v2_spec.md)
- Check the [Zrb Status Dashboard](https://status.zrb.dev)
- Join the developer channel: `#zrb-migration` on our Slack workspace
