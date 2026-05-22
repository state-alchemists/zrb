# Zrb CLI v1 → v2 Migration Guide

Zrb v2 introduces projects, paginated list endpoints, stricter authentication, and several field renames. Every breaking change is covered below with before/after examples.

**Audience:** Developers migrating an existing v1 integration.
**Time to read:** ~5 minutes.

---

## Breaking Changes at a Glance

| # | Change | v1 | v2 |
|---|--------|----|----|
| 1 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 2 | Auth header | `X-Auth-Token` | `Authorization: Bearer` |
| 3 | Task ID type | Integer | UUID string |
| 4 | Completion field | `done` | `completed` |
| 5 | Required field | — | `project_id` |
| 6 | List response | Bare array | Paginated envelope |

---

## 1. Endpoint Prefix

All endpoints now live under `/v2/`. Requests to bare `/tasks` return HTTP 404.

**Before (v1):**

```http
GET /tasks
POST /tasks
GET /tasks/42
PUT /tasks/42
DELETE /tasks/42
```

**After (v2):**

```http
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 2. Authentication Header

The `X-Auth-Token` header has been replaced with a standard Bearer token. Requests using the old header receive **HTTP 401**.

**Before (v1):**

```http
X-Auth-Token: sk-abc123
```

**After (v2):**

```http
Authorization: Bearer sk-abc123
```

> Your existing API key remains valid — pass it as a Bearer token. No need to regenerate credentials unless you want to.

---

## 3. Task ID: Integer → UUID

Task IDs are now UUID strings. If your application stores, caches, or type-checks IDs as integers, update accordingly.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Impact:**
- URL path parameters now expect UUIDs (`GET /v2/tasks/<uuid>`)
- Integer comparisons (`id === 42`) no longer work — switch to string comparison
- If you use integer IDs as database foreign keys, re-key your lookup tables

---

## 4. `done` Renamed to `completed`

The field that tracks task completion is now `completed`. The old `done` field is absent from v2 responses; sending `done` in a request body has no effect.

**Before (v1) — Create / Update:**

```json
{
  "title": "Ship v2",
  "done": true
}
```

**After (v2) — Create / Update:**

```json
{
  "title": "Ship v2",
  "completed": true,
  "project_id": "proj_abc123"
}
```

**Client-side checklist:**
- Rename all references from `task.done` to `task.completed`
- Update any UI checkboxes or toggle handlers
- Audit serialisation/deserialisation logic for the old field name

---

## 5. `project_id` Is Now Required

Every task must belong to a project. The `project_id` field is required when creating a task. Omitting it returns **HTTP 422 Unprocessable Entity**.

**Before (v1) — Create task:**

```http
POST /tasks
Content-Type: application/json

{
  "title": "Buy milk"
}
```

**After (v2) — Create task:**

```http
POST /v2/tasks
Content-Type: application/json
Authorization: Bearer sk-abc123

{
  "title": "Buy milk",
  "project_id": "proj_abc123"
}
```

**Migration notes:**
- Use the **List Projects** endpoint (`GET /v2/projects`) to discover available project IDs
- If your workflow creates tasks without a known project, assign them to a default project (e.g., `proj_inbox`)
- Existing v1 tasks are automatically assigned to a legacy project during migration — see your admin dashboard for details

---

## 6. List Responses Return a Paginated Envelope

List endpoints no longer return a bare array. Instead, they return a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "c3d4...", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Client-side update:**
```javascript
// v1 — bare array
const tasks = await fetch("/tasks").then(r => r.json());
tasks.forEach(t => render(t));

// v2 — paginated envelope
const { items, total, next_cursor } = await fetch("/v2/tasks").then(r => r.json());
console.log(`Showing ${items.length} of ${total} tasks`);
items.forEach(t => render(t));
```

**Pagination example:**

```python
# v2 — iterate pages with cursor
import requests

url = "https://api.zrb.dev/v2/tasks"
params = {"limit": 20}

while url:
    resp = requests.get(url, headers={"Authorization": "Bearer <token>"}, params=params)
    data = resp.json()
    for task in data["items"]:
        process(task)
    url = data["next_cursor"] and f"{url.split('?')[0]}?cursor={data['next_cursor']}"
```

> A `next_cursor` of `null` means there are no more pages.

---

## Step-by-Step Migration Checklist

- [ ] **Update auth headers.** Replace `X-Auth-Token` with `Authorization: Bearer` in every request.
- [ ] **Prefix all endpoint paths** with `/v2/`.
- [ ] **Replace integer IDs with UUIDs.** Update URL templates, path builders, and any ID type assertions.
- [ ] **Rename `done` to `completed`** in request bodies, response parsers, and client-side state.
- [ ] **Add `project_id` to every Create Task call.** Verify the field is non-null before sending.
- [ ] **Update list response handlers.** Unwrap the paginated envelope — read from `items`, `total`, and `next_cursor`.
- [ ] **Add cursor-based pagination** if you fetch more than one page of results.
- [ ] **Run integration tests** against a v2 staging environment before cutting over.
- [ ] **Monitor 401 and 422 responses** in logs during the cutover window — these point to stale auth headers or missing `project_id`.

---

## Upgrade Command

```bash
zrb upgrade --version 2
```

Or, for a clean install:

```bash
npm install -g zrb@latest   # npm
pip install --upgrade zrb   # pip
brew upgrade zrb            # Homebrew
```

Once upgraded, verify your installation:

```bash
zrb --version
# → zrb 2.0.0
```
