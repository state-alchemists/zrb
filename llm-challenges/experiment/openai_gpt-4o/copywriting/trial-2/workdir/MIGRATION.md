# Zrb Task API — v2 Migration Guide

Zrb v2 introduces projects, paginated responses, UUID-based identifiers, and stricter authentication. This guide covers every breaking change between v1 and v2, with before/after examples to get you up to speed quickly.

---

## 1. API Version Prefix

v2 requires all endpoints to be prefixed with `/v2/`. Old paths will return HTTP 404.

**Before (v1)**

```
GET /tasks
POST /tasks
GET /tasks/{id}
PUT /tasks/{id}
DELETE /tasks/{id}
```

**After (v2)**

```
GET /v2/tasks
POST /v2/tasks
GET /v2/tasks/{id}
PUT /v2/tasks/{id}
DELETE /v2/tasks/{id}
```

---

## 2. Authentication

The `X-Auth-Token` header is replaced with a standard Bearer token. Requests using the old header will receive HTTP 401.

**Before (v1)**

```
X-Auth-Token: <your_api_key>
```

**After (v2)**

```
Authorization: Bearer <your_api_token>
```

---

## 3. Task ID — Integer to UUID

Task IDs are now UUID strings instead of auto-incrementing integers. Any cached IDs from v1 will need to be re-retrieved.

**Before (v1)**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2)**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Update any stored references, URL builders, and type assertions to handle string UUIDs instead of integers.

---

## 4. Field Rename: `done` → `completed`

The `done` boolean field on task objects has been renamed to `completed`. Existing v1 data in the database is not migrated automatically — tasks created before the upgrade will report their status under `completed`.

**Before (v1)**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": true
}
```

```bash
curl -X PUT /tasks/42 \
  -H "X-Auth-Token: <key>" \
  -d '{"done": true}'
```

**After (v2)**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true
}
```

```bash
curl -X PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer <token>" \
  -d '{"completed": true}'
```

> **Client impact:** All request bodies and response parsers that reference `done` must be updated to `completed`.

---

## 5. Required Field: `project_id`

Task creation now requires `project_id`. Omitting it returns HTTP 422 Unprocessable Entity. Obtain a valid project ID from your workspace administrator or the project listing endpoint.

**Before (v1)**

```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2)**

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

> **Client impact:** Update all task creation flows to prompt for or default `project_id`. Existing automation scripts that call `POST /tasks` with only a title will break.

---

## 6. List Response — Bare Array to Paginated Envelope

v1 list endpoints returned a raw JSON array. v2 returns a paginated envelope with metadata, enabling cursor-based pagination.

**Before (v1)**

```json
GET /tasks
→
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2)**

```json
GET /v2/tasks?limit=20
→
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "created_at": "..."},
    {"id": "e5f6a7b8-...", "title": "Ship v2", "completed": true, "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Iterate over `items` instead of the top-level array. Use `next_cursor` to fetch the next page:

```bash
GET /v2/tasks?cursor=cursor_xyz&limit=20
```

> **Client impact:** Replace any code that iterates over the raw response array with code that reads `response.items`. Add cursor handling if you need full dataset traversal.

---

## Migration Checklist

Follow these steps in order. Tick each off as you go.

- [ ] **Update endpoint URLs** — Prepend `/v2/` to all Zrb API paths in your application and scripts.
- [ ] **Update authentication** — Replace `X-Auth-Token` headers with `Authorization: Bearer <token>`. Rotate any exposed API keys.
- [ ] **Re-fetch task IDs** — v2 uses UUIDs, not integers. Clear any cached integer IDs and retrieve them via the list endpoint.
- [ ] **Add `project_id` to create flows** — Update all task creation code to include a `project_id` field. Add validation that `project_id` is non-empty.
- [ ] **Rename `done` to `completed`** — Update request payloads, response parsers, and client-side models.
- [ ] **Adapt list response parsing** — Switch from bare-array iteration to `response.items`. Add pagination logic if your integration fetches more than 20 records.
- [ ] **Update type assertions** — If your code validates `typeof id === "number"`, update to accept string UUIDs. Update OpenAPI / client SDK specs.
- [ ] **Test against a staging environment** — Run your integration tests against the v2 endpoint before deploying to production.
- [ ] **Verify data integrity** — Confirm that migrated tasks have accurate `completed` values and valid `project_id` assignments.

---

## Upgrade

Install or update to the latest Zrb CLI to start using v2:

```bash
pip install --upgrade zrb-cli
```

Verify the installation:

```bash
zrb --version
# Expected: 2.x.x
```

For questions or issues, open a GitHub discussion at [github.com/state-alchemists/zrb/discussions](https://github.com/state-alchemists/zrb/discussions).
