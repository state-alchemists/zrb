# Zrb CLI v1 → v2 Migration Guide

**Audience:** Developers currently using the v1 Task API.
**Goal:** Upgrade your integration to v2 with minimal downtime.

v2 introduces projects, cursor-based pagination, and stricter authentication standards. There are **six breaking changes** — every one is covered below with a before/after example.

---

## Breaking Changes at a Glance

| # | Area | v1 | v2 |
|---|------|----|----|
| 1 | Endpoint prefix | `/tasks` | `/v2/tasks` |
| 2 | Authentication | `X-Auth-Token` header | `Authorization: Bearer` header |
| 3 | Task ID type | Integer (`42`) | UUID string (`"a1b2c3d4-..."`) |
| 4 | Completion field | `done` (boolean) | `completed` (boolean) |
| 5 | Task creation | Only `title` required | `title` + `project_id` required |
| 6 | List response | Bare array | Paginated envelope |

---

## 1. Endpoint Prefix

**Change:** All endpoints are now mounted under `/v2/`.

| Action | v1 | v2 |
|--------|----|----|
| List | `GET /tasks` | `GET /v2/tasks` |
| Get | `GET /tasks/{id}` | `GET /v2/tasks/{id}` |
| Create | `POST /tasks` | `POST /v2/tasks` |
| Update | `PUT /tasks/{id}` | `PUT /v2/tasks/{id}` |
| Delete | `DELETE /tasks/{id}` | `DELETE /v2/tasks/{id}` |

**v1 code:**

```python
response = requests.get("https://api.zrb.dev/tasks")
```

**v2 code:**

```python
response = requests.get("https://api.zrb.dev/v2/tasks")
```

The v1 paths will continue to serve existing clients for a deprecation window but will return a `Warning` header. Plan to migrate fully once your integration is updated.

---

## 2. Authentication Header

**Change:** The header changed from `X-Auth-Token` to the standard `Authorization: Bearer` scheme. Requests using the old header receive HTTP 401.

**v1 code:**

```python
headers = {"X-Auth-Token": "<your_api_key>"}
```

**v2 code:**

```python
headers = {"Authorization": "Bearer <your_api_token>"}
```

You may need to generate a new token — API keys are not interchangeable with Bearer tokens. Check the [Auth docs](https://docs.zrb.dev/auth) to obtain or rotate your token.

---

## 3. Task ID Type (Integer → UUID)

**Change:** The `id` field is now a UUID string instead of an auto-incrementing integer. All endpoints that accept an `id` parameter now expect the UUID format.

**v1 response:**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**v2 response:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Impact on client code:**

- If you stored task IDs as integers in a local database, you will need to migrate the column type to `UUID` or `TEXT`.
- If you sorted tasks by numeric ID, switch to sorting by `created_at`.
- References to tasks in URLs or UI components must now handle the longer UUID format.

**v1 code:**

```python
task_id = 42
response = requests.get(f"https://api.zrb.dev/tasks/{task_id}")
```

**v2 code:**

```python
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
response = requests.get(f"https://api.zrb.dev/v2/tasks/{task_id}")
```

---

## 4. Field Rename: `done` → `completed`

**Change:** The `done` boolean field has been renamed to `completed`. The semantics remain the same (`true` = task is finished).

**v1 code (reading):**

```python
if task["done"]:
    print("Task is complete")
```

**v2 code (reading):**

```python
if task["completed"]:
    print("Task is complete")
```

**v1 code (writing — update):**

```python
requests.put(f"https://api.zrb.dev/tasks/{id}", json={"done": True})
```

**v2 code (writing — update):**

```python
requests.put(f"https://api.zrb.dev/v2/tasks/{id}", json={"completed": True})
```

> **Migration tip:** Grep your codebase for `["done"]`, `['done']`, and `.done` in task-handling code. Every occurrence must change to `completed`.

---

## 5. Task Creation Now Requires `project_id`

**Change:** Creating a task now requires a `project_id` field. Omitting it returns HTTP 422 Unprocessable Entity.

**v1 code:**

```python
response = requests.post("https://api.zrb.dev/tasks", json={
    "title": "New task"
})
print(response.status_code)  # 201
```

**v2 code:**

```python
response = requests.post("https://api.zrb.dev/v2/tasks", json={
    "title": "New task",
    "project_id": "proj_abc123"
})
print(response.status_code)  # 201
```

**Migration steps:**

1. Identify which project each new task should belong to.
2. If you have a single-project setup, create a default project via the v2 API and hardcode or configure its ID.
3. If your application lets users organise tasks, add a project-picker UI or assign a fallback project.
4. Update any automated task-creation scripts to include `project_id`.

---

## 6. List Response Format (Bare Array → Paginated Envelope)

**Change:** List endpoints no longer return a bare JSON array. They return a paginated envelope with `items`, `total`, and `next_cursor`.

**v1 code (list tasks):**

```python
response = requests.get("https://api.zrb.dev/tasks")
tasks = response.json()  # direct array
for task in tasks:
    print(task["title"])
```

**v2 code (list tasks, first page):**

```python
response = requests.get("https://api.zrb.dev/v2/tasks", params={"limit": 50})
data = response.json()
tasks = data["items"]      # the array lives under "items"
total = data["total"]      # total count across all pages
next_cursor = data.get("next_cursor")  # None if last page
```

**v2 code (list tasks, subsequent pages):**

```python
cursor = None
while True:
    params = {"limit": 50}
    if cursor:
        params["cursor"] = cursor
    response = requests.get("https://api.zrb.dev/v2/tasks", params=params)
    data = response.json()
    for task in data["items"]:
        process(task)
    cursor = data.get("next_cursor")
    if not cursor:
        break
```

**Impact on client code:**

- Replace `.json()` with `.json()["items"]` on all list calls.
- If your UI displays a total count, use `data["total"]`.
- If your app loaded every task at once, switch to cursor-based iteration (see above) to handle large result sets.

---

## Migration Checklist

Use this order to minimise breakage during the rollout:

- [ ] **Generate Bearer tokens** — obtain v2-compatible tokens for every environment (dev, staging, prod).
- [ ] **Migrate local task ID storage** — if you cache task IDs in a database, update the column to UUID/TEXT. Backfill existing integer IDs if needed.
- [ ] **Update endpoint URLs** — prepend `/v2/` to every request path.
- [ ] **Update auth headers** — replace `X-Auth-Token` with `Authorization: Bearer`.
- [ ] **Replace `done` with `completed`** — audit reads and writes across the entire codebase.
- [ ] **Add `project_id` to task creation** — configure a default project ID and pass it on every `POST`.
- [ ] **Refactor list response parsing** — unwrap the envelope: `.json()["items"]`, and implement cursor-based pagination.
- [ ] **Update API client or SDK** — if you maintain a thin wrapper, bump its version and update all calls.
- [ ] **Run integration tests** — cycle through every CRUD operation against a v2 staging environment.
- [ ] **Deploy to staging** — verify the full workflow before cutting over production.

---

## Upgrade Command

Once your codebase is updated, authenticate with your new Bearer token and verify the API responds correctly:

```bash
curl -H "Authorization: Bearer <your_api_token>" https://api.zrb.dev/v2/tasks?limit=1
```

You should receive a `200` with a paginated envelope.
