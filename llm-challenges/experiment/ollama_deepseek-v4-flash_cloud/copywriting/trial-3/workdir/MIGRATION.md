# Zrb Task API — v1 to v2 Migration Guide

**Audience:** developers currently integrating with the v1 Task API
**Goal:** upgrade your integration to v2 with minimal downtime

v2 introduces projects, cursor-based pagination, stricter authentication, and a
cleaner data model. Every breaking change is covered below with its migration
path.

---

## At a Glance — All Breaking Changes

| # | Change | Impact |
|---|--------|--------|
| 1 | All endpoints prefixed with `/v2/` | Update URL paths |
| 2 | `X-Auth-Token` header replaced by `Authorization: Bearer` | Regenerate credentials, update auth logic |
| 3 | Task `id` type: integer → UUID string | Update ID storage, URL construction, type checks |
| 4 | Field `done` renamed to `completed` | Update serialization/deserialization code |
| 5 | `project_id` required on task creation | Add project assignment to create flows |
| 6 | List endpoints return paginated envelope instead of bare array | Update response parsing and add cursor handling |

---

## Breaking Change 1 — Endpoint Paths

**v1** — no version prefix:

```http
GET /tasks
POST /tasks
GET /tasks/42
PUT /tasks/42
DELETE /tasks/42
```

**v2** — all endpoints are prefixed with `/v2/`:

```http
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
DELETE /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Migration:** update your base URL or endpoint paths. The old paths will not
redirect — they return HTTP 404.

---

## Breaking Change 2 — Authentication Header

**v1** — API key in a custom header:

```http
X-Auth-Token: sk_live_abc123
```

**v2** — Bearer token:

```http
Authorization: Bearer zrb_live_xyz789
```

**Migration:**
1. Generate a new Bearer token from the Zrb dashboard (v1 API keys do not carry over).
2. Replace the `X-Auth-Token` header with `Authorization: Bearer <token>` in all requests.
3. Remove any `X-Auth-Token` header logic from your client.

Requests using the old header receive HTTP 401.

---

## Breaking Change 3 — Task ID Type (Integer → UUID)

**v1** — integer IDs:

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**v2** — UUID string IDs:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

**Migration:**
- Change `id` column/storage from integer to UUID string (e.g., `TEXT` in SQL,
  `string` in TypeScript/Go/Python).
- Update URL construction: `GET /v2/tasks/${id}` where `id` is now a string.
- Remove any integer-based assumptions (auto-increment, numeric range checks,
  `parseInt` calls).
- Existing v1 IDs are **not** reused in v2 — seed your migration with a
  mapping table if you need to reference legacy records.

---

## Breaking Change 4 — Field Rename: `done` → `completed`

**v1:**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": true
}
```

**v2:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true
}
```

**Migration:**

```python
# v1
task["done"] = True

# v2
task["completed"] = True
```

```javascript
// v1
if (response.done) { ... }

// v2
if (response.completed) { ... }
```

The `done` field is absent from v2 responses. Write-side (`PUT`) also uses
`completed` — sending `done` has no effect.

---

## Breaking Change 5 — `project_id` Required on Creation

**v1** — only `title` is needed:

```http
POST /tasks
Content-Type: application/json

{
  "title": "Deploy monitoring"
}
```

**v2** — must also include `project_id`:

```http
POST /v2/tasks
Content-Type: application/json
Authorization: Bearer zrb_live_xyz789

{
  "title": "Deploy monitoring",
  "project_id": "proj_abc123"
}
```

**Migration:**
- Update your task creation UI or API to collect/assign a `project_id`.
- Obtain the `project_id` from `GET /v2/projects` (new v2 endpoint) or your
  application context.
- Omitting `project_id` returns HTTP 422 with an error body.

---

## Breaking Change 6 — Paginated List Envelope

**v1** — bare array:

```http
GET /tasks
```

```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**v2** — paginated envelope:

```http
GET /v2/tasks?limit=20&cursor=
```

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false},
    {"id": "d3e4...", "title": "Ship v2", "completed": true}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Migration:**

```python
# v1
tasks = response.json()
for t in tasks:
    print(t["title"])

# v2
body = response.json()
tasks = body["items"]
total = body["total"]  # total across all pages
next_cursor = body["next_cursor"]  # None if last page
for t in tasks:
    print(t["title"])

# Paginate:
cursor = None
while True:
    params = {"limit": 20}
    if cursor:
        params["cursor"] = cursor
    resp = client.get("/v2/tasks", params=params)
    body = resp.json()
    tasks.extend(body["items"])
    cursor = body.get("next_cursor")
    if not cursor:
        break
```

Default page size is 20; pass `?limit=` to adjust (max 100).

---

## Step-by-Step Migration Checklist

- [ ] **1. Generate Bearer token** — create a new Bearer token in the Zrb
      dashboard. Revoke old v1 API keys after confirming v2 works.
- [ ] **2. Update base URL** — append `/v2` to all endpoint paths.
- [ ] **3. Replace auth header** — swap `X-Auth-Token` for
      `Authorization: Bearer <token>`.
- [ ] **4. Migrate ID storage** — change task IDs from integer to UUID string.
      Build a mapping table if legacy references are needed.
- [ ] **5. Rename `done` to `completed`** — update all read and write paths.
- [ ] **6. Add `project_id`** — extend task creation to accept and send
      `project_id`. Fetch available projects via `GET /v2/projects`.
- [ ] **7. Rewrite list parsing** — handle the paginated envelope. Add cursor
      state to your list fetchers.
- [ ] **8. Test create, update, delete** — verify full CRUD against v2 staging.
- [ ] **9. Test pagination** — fetch 2+ pages, confirm `next_cursor` cycles and
      terminates with `None`.
- [ ] **10. Audit error handling** — check for HTTP 401 (bad auth), 422
      (missing `project_id`), and 404 (old paths).
- [ ] **11. Deploy and monitor** — roll out to production; watch for 401/422
      spikes; keep your v1 credentials until the cutover window closes.

---

## Upgrade Command

Install the latest Zrb CLI to start using the v2 API:

```bash
pip install --upgrade zrb
```

Verify the version:

```bash
zrb --version
# zrb 2.x.x
```

Once upgraded and migrated, your existing v1 integration will break — confirm
all checklist items before deploying to production.
