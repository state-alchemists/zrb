# Zrb CLI v1 → v2 Migration Guide

Zrb v2 brings projects, pagination, and stronger security conventions. Every breaking change is documented below with before/after examples so you can migrate with confidence.

---

## Table of Contents

1. [Authentication Header Changed](#1-authentication-header-changed)
2. [All Endpoints Now Use `/v2/` Prefix](#2-all-endpoints-now-use-v2-prefix)
3. [Task IDs Are UUIDs Instead of Integers](#3-task-ids-are-uuids-instead-of-integers)
4. [`done` Renamed to `completed`](#4-done-renamed-to-completed)
5. [Task Creation Requires `project_id`](#5-task-creation-requires-project_id)
6. [List Responses Are Now Paginated](#6-list-responses-are-now-paginated)
7. [Step-by-Step Migration Checklist](#7-step-by-step-migration-checklist)
8. [Upgrade Command](#8-upgrade-command)

---

## 1. Authentication Header Changed

**Impact:** All existing API calls with `X-Auth-Token` will receive HTTP 401. You must switch to a Bearer token.

**Before (v1):**

```
X-Auth-Token: <your_api_key>
```

**After (v2):**

```
Authorization: Bearer <your_api_token>
```

**Client examples:**

```python
# v1 — broken in v2
headers = {"X-Auth-Token": "abc123"}
requests.get("https://api.zrb.dev/tasks", headers=headers)
```

```python
# v2
headers = {"Authorization": "Bearer abc123"}
requests.get("https://api.zrb.dev/v2/tasks", headers=headers)
```

```bash
# v1 — broken in v2
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks

# v2
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

---

## 2. All Endpoints Now Use `/v2/` Prefix

**Impact:** Every route is now under `/v2/`. Old routes return HTTP 404.

| Endpoint | v1 | v2 |
|---|---|---|
| List tasks | `GET /tasks` | `GET /v2/tasks` |
| Get task | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create task | `POST /tasks` | `POST /v2/tasks` |
| Update task | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete task | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**Before (v1):**

```python
resp = requests.get("https://api.zrb.dev/tasks", headers=headers)
```

**After (v2):**

```python
resp = requests.get("https://api.zrb.dev/v2/tasks", headers=headers)
```

---

## 3. Task IDs Are UUIDs Instead of Integers

**Impact:** Any code that stores, compares, or references task IDs as integers will break. IDs are now UUID strings like `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`.

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

**Client impact:**

```python
# v1 — broken in v2
task_id = response.json()["id"]       # int — 42
url = f"https://api.zrb.dev/tasks/{task_id}"
```

```python
# v2
task_id = response.json()["id"]       # str — "a1b2c3d4-..."
url = f"https://api.zrb.dev/v2/tasks/{task_id}"
```

> **Note:** If you store task IDs in a database, you will need to migrate the column type from integer to UUID.

---

## 4. `done` Renamed to `completed`

**Impact:** Any code reading or writing the `done` field must use `completed` instead. The old field will not appear in responses.

**Before (v1):**

```python
task = response.json()
is_done = task["done"]                 # reads the old field
```

```python
# v1 — creating/updating
payload = {"title": "Ship v2", "done": true}
requests.put("https://api.zrb.dev/tasks/42", json=payload, headers=headers)
```

**After (v2):**

```python
task = response.json()
is_done = task["completed"]            # reads the new field
```

```python
# v2
payload = {"title": "Ship v2", "completed": true}
requests.put("https://api.zrb.dev/v2/tasks/a1b2c3d4-...", json=payload, headers=headers)
```

---

## 5. Task Creation Requires `project_id`

**Impact:** `POST /v2/tasks` now requires a `project_id` field. Omitting it returns HTTP 422. Retrieve valid project IDs from `GET /v2/projects`.

**Before (v1):**

```json
POST /tasks
{
  "title": "New task title"
}
```

**After (v2):**

```json
POST /v2/tasks
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

**Client impact:**

```python
# v1 — broken in v2
payload = {"title": "New task title"}

# v2
payload = {"title": "New task title", "project_id": "proj_abc123"}
resp = requests.post("https://api.zrb.dev/v2/tasks", json=payload, headers=headers)
```

> If you don't know which project to use, list available projects:
> ```bash
> curl -H "Authorization: Bearer <token>" https://api.zrb.dev/v2/projects
> ```

---

## 6. List Responses Are Now Paginated

**Impact:** `GET /v2/tasks` no longer returns a bare array. It returns a paginated envelope. All code iterating over the response directly will break.

**Before (v1) — bare array:**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2) — paginated envelope:**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Client impact:**

```python
# v1 — broken in v2
tasks = response.json()                        # bare array
for task in tasks:
    print(task["title"])
```

```python
# v2 — single page
envelope = response.json()
tasks = envelope["items"]                      # nested under "items"
total = envelope["total"]                      # server-side total count
for task in tasks:
    print(task["title"])

# v2 — full pagination
def fetch_all_tasks():
    tasks = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get("https://api.zrb.dev/v2/tasks", params=params, headers=headers)
        envelope = resp.json()
        tasks.extend(envelope["items"])
        cursor = envelope.get("next_cursor")
        if not cursor:
            break
    return tasks
```

---

## 7. Step-by-Step Migration Checklist

Follow these steps in order. Each step is independently testable.

- [ ] **1. Update authentication.** Replace every instance of `X-Auth-Token` with `Authorization: Bearer <token>`. Regenerate tokens if needed via the dashboard.
- [ ] **2. Update all endpoint URLs.** Prepend `/v2` to every route: `/tasks` → `/v2/tasks`, `/tasks/{id}` → `/v2/tasks/{id}`, etc.
- [ ] **3. Rename `done` to `completed`.** Search your codebase for all reads and writes of `task["done"]` and update them to `task["completed"]`.
- [ ] **4. Add `project_id` to task creation.** Identify what project your tasks belong to and hardcode or resolve a `project_id` value before posting.
- [ ] **5. Handle UUID IDs.** Ensure any code that stores, serializes, or compares task IDs handles strings instead of integers. Migrate database columns if applicable.
- [ ] **6. Rewrite list-response consumers.** Update all code reading `GET /tasks` responses to unwrap the paginated envelope. Implement cursor-based pagination if you need more than one page.
- [ ] **7. Smoke-test the happy path.** Create a task, list tasks, update it, fetch it by ID, and delete it — all against the v2 API.
- [ ] **8. Run your test suite.** Fix remaining failures from any missed field names, ID types, or header formats.

---

## 8. Upgrade Command

Once your code is migrated, update your Zrb CLI dependency:

```bash
pip install zrb>=2.0.0
```

Or if you use a `requirements.txt` / `pyproject.toml`:

```
zrb>=2.0.0
```

Verify the installation:

```bash
zrb --version
# → Zrb v2.x.x
```

---

> **Questions?** Open an issue at https://github.com/state-alchemists/zrb/issues or start a discussion in the community forum.
