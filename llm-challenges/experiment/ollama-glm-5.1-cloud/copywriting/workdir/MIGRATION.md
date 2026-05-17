# Migrating from Zrb Task API v1 to v2

v2 introduces projects, cursor-based pagination, and stricter authentication. Every v1 integration will break without changes. This guide covers each breaking change with before/after examples so you can update your code quickly.

---

## Breaking Changes

### 1. All endpoints moved to `/v2/` prefix

Every v1 endpoint path must be prefixed with `/v2`. The old paths return 404.

**Before (v1):**
```bash
curl https://api.zrb.dev/tasks
```

**After (v2):**
```bash
curl https://api.zrb.dev/v2/tasks
```

This applies to all endpoints: `/v2/tasks`, `/v2/tasks/{id}`, etc.

---

### 2. Authentication header changed

The `X-Auth-Token` header is rejected with HTTP 401 in v2. Replace it with a standard `Authorization: Bearer` header.

**Before (v1):**
```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

```python
# Python
headers = {"X-Auth-Token": API_KEY}
```

```javascript
// JavaScript
const headers = { "X-Auth-Token": apiKey };
```

**After (v2):**
```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

```python
# Python
headers = {"Authorization": f"Bearer {API_KEY}"}
```

```javascript
// JavaScript
const headers = { Authorization: `Bearer ${apiKey}` };
```

---

### 3. Task `id` changed from integer to UUID string

Task IDs are now UUIDs, not auto-incrementing integers. Any code that assumes numeric IDs (e.g., iterating, comparing with `<`, parsing as `int`) must be updated.

**Before (v1):**
```json
{"id": 42, "title": "Write tests", "done": false, "created_at": "..."}
```

**After (v2):**
```json
{"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Write tests", "completed": false, "project_id": "proj_abc123", "created_at": "..."}
```

```python
# Before — v1
task_id: int = response["id"]

# After — v2
task_id: str = response["id"]
```

```javascript
// Before — v1
const taskId = Number(response.id);

// After — v2
const taskId = response.id; // already a string
```

---

### 4. Task field `done` renamed to `completed`

The `done` field no longer exists in v2 responses or request bodies. Use `completed` instead.

**Before (v1):**
```json
{"done": true}
```

**After (v2):**
```json
{"completed": true}
```

```python
# Before — v1
if task["done"]:
    print("Task finished!")

# After — v2
if task["completed"]:
    print("Task finished!")
```

```javascript
// Before — v1
if (task.done) { /* ... */ }

// After — v2
if (task.completed) { /* ... */ }
```

When updating a task, use `completed` in the request body:

```bash
# Before — v1
curl -X PUT -d '{"done": true}' https://api.zrb.dev/tasks/42

# After — v2
curl -X PUT -d '{"completed": true}' https://api.zrb.dev/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 5. `project_id` is now required when creating tasks

v2 requires a `project_id` on every `POST /v2/tasks` request. Omitting it returns HTTP 422.

**Before (v1):**
```json
{
  "title": "New task title"
}
```

**After (v2):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

```python
# Before — v1
response = client.post("/tasks", json={"title": "Write tests"})

# After — v2
response = client.post("/v2/tasks", json={
    "title": "Write tests",
    "project_id": "proj_abc123"
})
```

```javascript
// Before — v1
await fetch("/tasks", {
  method: "POST",
  body: JSON.stringify({ title: "Write tests" })
});

// After — v2
await fetch("/v2/tasks", {
  method: "POST",
  body: JSON.stringify({ title: "Write tests", project_id: "proj_abc123" })
});
```

---

### 6. List endpoints return a paginated envelope

v1 returned a bare array. v2 wraps results in a pagination envelope with `items`, `total`, and `next_cursor`. Any code that treats the response as a bare array will break.

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
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

```python
# Before — v1
tasks = response.json()  # returns a list directly
for task in tasks:
    print(task["title"])

# After — v2
data = response.json()
for task in data["items"]:
    print(task["title"])

# To fetch all pages:
cursor = None
while True:
    params = {"cursor": cursor} if cursor else {}
    data = client.get("/v2/tasks", params=params).json()
    for task in data["items"]:
        print(task["title"])
    cursor = data.get("next_cursor")
    if not cursor:
        break
```

```javascript
// Before — v1
const tasks = await response.json(); // array directly
tasks.forEach(t => console.log(t.title));

// After — v2
const { items, next_cursor } = await response.json();
items.forEach(t => console.log(t.title));

// To fetch all pages:
let cursor = null;
while (true) {
  const url = cursor
    ? `/v2/tasks?cursor=${cursor}`
    : `/v2/tasks`;
  const { items, next_cursor } = await fetch(url).then(r => r.json());
  items.forEach(t => console.log(t.title));
  if (!next_cursor) break;
  cursor = next_cursor;
}
```

**Query parameters** for controlling pagination:
- `limit` — max results per page (default 20)
- `cursor` — pass `next_cursor` from the previous response to fetch the next page

---

## Migration Checklist

Work through these items in order. Each maps to a breaking change above.

- [ ] **Update the base URL** — add `/v2` prefix to every endpoint path
- [ ] **Update auth headers** — replace `X-Auth-Token` with `Authorization: Bearer` in all requests
- [ ] **Update ID handling** — change task ID types from `int` to `str`/`string`; remove any integer-specific logic (comparisons, casting, iteration by incrementing)
- [ ] **Rename `done` to `completed`** — search your codebase for `done` in task contexts (responses, request bodies, conditionals, serialisation) and replace with `completed`
- [ ] **Add `project_id` to create calls** — every `POST /v2/tasks` body must include `project_id`; confirm you have a way to determine the project before creating tasks
- [ ] **Update list-endpoint parsing** — change all list-endpoint consumers to read from the `.items` key instead of treating the response as a bare array
- [ ] **Implement cursor pagination** — if you fetch multiple pages or all results, add a loop that follows `next_cursor`; remove any offset-based or length-based pagination logic
- [ ] **Test with v2** — run your integration against the v2 API and verify each endpoint works before switching production traffic

---

Upgrade now:

```bash
pip install --upgrade zrb
```