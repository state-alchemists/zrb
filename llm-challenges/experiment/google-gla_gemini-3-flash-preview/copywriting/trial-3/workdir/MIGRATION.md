# Zrb Task API — v1 to v2 Migration Guide

Zrb v2 introduces projects, cursor-based pagination, and stricter authentication. The API surface has been cleaned up with several intentional breaking changes. This guide covers everything you need to update your integrations.

---

## Breaking Changes at a Glance

| # | Change | Impact |
|---|--------|--------|
| 1 | Endpoints prefixed with `/v2/` | All URL paths change |
| 2 | Authentication header changed | Every request must be updated |
| 3 | Task `id` is now a UUID string | Replace integer lookups and storage |
| 4 | Task `done` renamed to `completed` | Read/write code must use new field |
| 5 | `project_id` required on create | New field must be provided |
| 6 | List responses now paginated | Response shape and access pattern changed |

---

## 1. Endpoint Paths Prefixed with `/v2/`

All endpoints now live under `/v2/`. Requests to v1 paths will fail.

**Before (v1):**

```
POST /tasks
GET /tasks/42
```

**After (v2):**

```
POST /v2/tasks
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Update your base URL or path construction to include the `/v2/` prefix.

---

## 2. Authentication Header Changed

The `X-Auth-Token` header has been replaced with a standard Bearer token. Requests using the old header will receive HTTP 401.

**Before (v1):**

```python
headers = {
    "X-Auth-Token": "your_api_key"
}
```

**After (v2):**

```python
headers = {
    "Authorization": "Bearer your_api_token"
}
```

Generate a new API token from your account dashboard — v1 keys are **not** forward-compatible.

---

## 3. Task `id` Changed from Integer to UUID String

Task identifiers are now UUID v4 strings. Any code that relies on integer IDs — for lookups, storage, or comparison — must be updated.

**Before (v1):**

```python
task_id = 42
response = requests.get(f"https://api.zrb.dev/tasks/{task_id}")
```

**After (v2):**

```python
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
response = requests.get(f"https://api.zrb.dev/v2/tasks/{task_id}")
```

Existing integer IDs are **not** reused in v2. You must map old IDs to new UUIDs via the migration endpoint (see [Migration Checklist](#step-6-run-the-data-migration) below).

---

## 4. Task Field `done` Renamed to `completed`

The boolean field `done` has been renamed to `completed`. The semantics are identical.

**Before (v1):**

```python
# Reading
if task["done"]:
    print("Task is complete")

# Writing
payload = {"done": True}
```

```json
// Response (v1)
{"id": 42, "title": "Write tests", "done": false, "created_at": "..."}
```

**After (v2):**

```python
# Reading
if task["completed"]:
    print("Task is complete")

# Writing
payload = {"completed": True}
```

```json
// Response (v2)
{"id": "a1b2c3d4-...", "title": "Write tests", "completed": false, "project_id": "proj_abc123", "created_at": "..."}
```

Audit every read and write path in your code for the `done` key and replace it with `completed`.

---

## 5. `project_id` Required When Creating Tasks

Every task must now belong to a project. The `project_id` field is required on `POST /v2/tasks`. Omitting it returns HTTP 422.

**Before (v1):**

```python
payload = {"title": "Write tests"}
response = requests.post("https://api.zrb.dev/tasks", json=payload)
```

**After (v2):**

```python
payload = {
    "title": "Write tests",
    "project_id": "proj_abc123"
}
response = requests.post("https://api.zrb.dev/v2/tasks", json=payload)
```

Create a default project (e.g., "General") if you don't use projects yet. Every v2 task references a project via `project_id`.

---

## 6. List Responses Return a Paginated Envelope

The bare array response has been replaced with a paginated envelope. Cursor-based pagination replaces offset/limit.

**Before (v1):**

```python
response = requests.get("https://api.zrb.dev/tasks")
tasks = response.json()  # bare array
for task in tasks:
    print(task["title"])
```

Response shape:

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2):**

```python
response = requests.get(
    "https://api.zrb.dev/v2/tasks",
    params={"limit": 20}
)
data = response.json()
tasks = data["items"]  # nested under "items"
for task in tasks:
    print(task["title"])

# Paginate
next_cursor = data.get("next_cursor")
while next_cursor:
    response = requests.get(
        "https://api.zrb.dev/v2/tasks",
        params={"cursor": next_cursor, "limit": 20}
    )
    data = response.json()
    tasks = data["items"]
    # ... process page ...
    next_cursor = data.get("next_cursor")
```

Response shape:

```json
{
  "items": [
    {"id": "a1b2c3d4-...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

Access items via `response["items"]`, not the response directly. Use `?cursor=` and `?limit=` for pagination instead of rolling your own offset logic. `total` gives you the full count across all pages.

---

## Step-by-Step Migration Checklist

Use this checklist to track your migration. Complete each step in order before moving to the next.

### Step 1: Generate New API Tokens
- [ ] Create Bearer tokens from your account dashboard
- [ ] Revoke old v1 `X-Auth-Token` keys
- [ ] Update environment variables and secrets stores

### Step 2: Update Base URL
- [ ] Change base path from `/` to `/v2/` in all API calls
- [ ] Update any hardcoded URLs in configuration files

### Step 3: Replace `done` with `completed`
- [ ] Search codebase for `["done"]` and `["done"]` references in request payloads
- [ ] Update all response parsers to read `completed` instead of `done`
- [ ] Update all mutation payloads to write `completed` instead of `done`

### Step 4: Handle UUID Task IDs
- [ ] Update database schemas to store UUID strings instead of integers
- [ ] Update all `GET /tasks/{id}`, `PUT /tasks/{id}`, and `DELETE /tasks/{id}` callers to pass UUIDs
- [ ] Update UI components that display or link task IDs

### Step 5: Add `project_id` to Task Creation
- [ ] Create at least one project via the Projects API or dashboard
- [ ] Update `POST /v2/tasks` callers to include `project_id`
- [ ] Add `project_id` to any task creation forms in your UI

### Step 6: Run the Data Migration
- [ ] Execute the migration script (see below) to map old integer IDs to new UUIDs
- [ ] Verify migrated tasks appear with correct titles and completed status under the correct project

```bash
zrb migrate tasks --target-project proj_abc123
```

### Step 7: Update List Response Handling
- [ ] Replace array iteration with `response["items"]` access
- [ ] Implement cursor-based pagination loop
- [ ] Remove any offset/limit pagination logic

### Step 8: Test Against Staging
- [ ] Point your integration at the v2 staging environment
- [ ] Run your full test suite
- [ ] Verify every CRUD operation works end-to-end

### Step 9: Deploy to Production
- [ ] Deploy updated application code
- [ ] Run the data migration in production
- [ ] Monitor for 401, 404, and 422 errors

---

## Upgrade Now

```bash
pip install zrb-cli>=2.0.0
zrb migrate tasks --target-project proj_abc123
```

For questions or migration support, see the [v2 changelog](https://docs.zrb.dev/changelog) or open an issue on GitHub.
