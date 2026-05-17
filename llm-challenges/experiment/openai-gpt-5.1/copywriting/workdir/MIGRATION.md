# Zrb Task API v1 → v2 Migration Guide

This guide helps you migrate existing Zrb Task API v1 integrations to v2. It assumes you already have working v1 code.

v2 adds projects, cursor-based pagination, and stricter authentication. It also introduces several breaking changes you must address before switching your clients to v2.

## Overview of Breaking Changes

1. All endpoints are now prefixed with `/v2/`
2. Authentication header changed from `X-Auth-Token` to `Authorization: Bearer ...`
3. Task `id` type changed from integer to UUID string
4. Task field `done` renamed to `completed`
5. Task creation now requires `project_id`
6. List endpoints return a paginated envelope instead of a bare array

The sections below walk through each breaking change with before/after examples.

---

## 1. Endpoint paths now use `/v2/` prefix

All task endpoints that previously lived at `/tasks` are now under `/v2/tasks`.

### Impact

Any hard-coded URLs or API client wrappers that point to `/tasks`, `/tasks/{id}`, etc. must be updated to `/v2/tasks`, `/v2/tasks/{id}`, and so on.

### Before (v1)

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
```

```http
GET /tasks/42 HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
```

```http
POST /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
Content-Type: application/json

{"title": "New task title"}
```

### After (v2)

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
```

```http
GET /v2/tasks/{id} HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
```

```http
POST /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
Content-Type: application/json

{"title": "New task title", "project_id": "proj_abc123"}
```

---

## 2. Authentication header changed

v1 used a custom header `X-Auth-Token`. v2 uses a standard Bearer token in the `Authorization` header. Requests that still use `X-Auth-Token` will receive HTTP 401.

### Action required

Update any HTTP client, middleware, or SDK code that injects authentication headers.

### Before (v1)

```http
GET /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: 123456
```

Example client code:

```js
// v1 node fetch wrapper
async function listTasks() {
  const res = await fetch('https://api.example.com/tasks', {
    headers: {
      'X-Auth-Token': process.env.ZRB_API_KEY,
    },
  });
  return res.json();
}
```

### After (v2)

```http
GET /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer 123456
```

Updated client code:

```js
// v2 node fetch wrapper
async function listTasks() {
  const res = await fetch('https://api.example.com/v2/tasks', {
    headers: {
      Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
    },
  });
  return res.json();
}
```

---

## 3. Task `id` type changed from integer to UUID string

In v1, `Task.id` was an integer. In v2, it is a UUID string. This affects URL path parameters, database schemas, and any type definitions or validations you have.

### Before (v1)

Task object:

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

Endpoint usage:

```http
GET /tasks/42 HTTP/1.1
X-Auth-Token: <your_api_key>
```

Example typed client code:

```ts
// v1 type
interface TaskV1 {
  id: number;
  title: string;
  done: boolean;
  created_at: string;
}

async function getTask(id: number): Promise<TaskV1> {
  const res = await fetch(`https://api.example.com/tasks/${id}`);
  return res.json();
}
```

### After (v2)

Task object:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Endpoint usage:

```http
GET /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Authorization: Bearer <your_api_token>
```

Updated typed client code:

```ts
// v2 type
interface TaskV2 {
  id: string; // UUID
  title: string;
  completed: boolean;
  project_id: string;
  created_at: string;
}

async function getTask(id: string): Promise<TaskV2> {
  const res = await fetch(`https://api.example.com/v2/tasks/${id}`, {
    headers: {
      Authorization: `Bearer ${process.env.ZRB_API_TOKEN}`,
    },
  });
  return res.json();
}
```

Where necessary, update your persistence layer (e.g., change integer columns to string/UUID) or store both old and new IDs during a transition period.

---

## 4. Task field `done` renamed to `completed`

The boolean field that tracks task completion was renamed from `done` to `completed`.

This affects:
- Response parsing (reading task state)
- Update payloads (writing task state)
- Any serialization/deserialization or mapping code

### Before (v1)

Task object:

```json
{
  "id": 42,
  "title": "Write tests",
  "done": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

Update request:

```http
PUT /tasks/42 HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "done": true
}
```

Example client code:

```python
# v1 python client snippet
@dataclass
class TaskV1:
    id: int
    title: str
    done: bool
    created_at: str


def complete_task(task_id: int) -> TaskV1:
    resp = requests.put(
        f"https://api.example.com/tasks/{task_id}",
        headers={"X-Auth-Token": API_KEY},
        json={"done": True},
    )
    resp.raise_for_status()
    return TaskV1(**resp.json())
```

### After (v2)

Task object:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": true,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Update request:

```http
PUT /v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "completed": true
}
```

Updated client code:

```python
# v2 python client snippet
@dataclass
class TaskV2:
    id: str
    title: str
    completed: bool
    project_id: str
    created_at: str


def complete_task(task_id: str) -> TaskV2:
    resp = requests.put(
        f"https://api.example.com/v2/tasks/{task_id}",
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        json={"completed": True},
    )
    resp.raise_for_status()
    return TaskV2(**resp.json())
```

Search your codebase for `done` to ensure you catch all usages.

---

## 5. Task creation now requires `project_id`

v2 introduces projects. Every task must now belong to a project, referenced by `project_id`. This field is required on task creation. Omitting it results in HTTP 422.

### Before (v1)

Create task request:

```http
POST /tasks HTTP/1.1
Host: api.example.com
X-Auth-Token: <your_api_key>
Content-Type: application/json

{
  "title": "New task title"
}
```

Example client code:

```ruby
# v1 ruby client snippet
class ClientV1
  def create_task(title)
    res = HTTP.headers("X-Auth-Token" => ENV["ZRB_API_KEY"]).post(
      "https://api.example.com/tasks",
      json: { title: title }
    )
    res.parse
  end
end
```

### After (v2)

Create task request (with required `project_id`):

```http
POST /v2/tasks HTTP/1.1
Host: api.example.com
Authorization: Bearer <your_api_token>
Content-Type: application/json

{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

Example updated client code:

```ruby
# v2 ruby client snippet
class ClientV2
  def create_task(title, project_id)
    res = HTTP.headers(
      "Authorization" => "Bearer #{ENV["ZRB_API_TOKEN"]}"
    ).post(
      "https://api.example.com/v2/tasks",
      json: { title: title, project_id: project_id }
    )
    res.parse
  end
end
```

Plan how your system will obtain and manage `project_id` values (e.g., configuration per environment, per user, or per workspace).

---

## 6. List endpoints now return a paginated envelope

In v1, `GET /tasks` returned a bare JSON array of tasks. In v2, `GET /v2/tasks` returns a paginated envelope with `items`, `total`, and `next_cursor`.

Your code must be updated to:
- Read `items` instead of assuming the response body is an array
- Optionally handle cursor-based pagination using `next_cursor` and the `cursor` query parameter

### Before (v1)

List tasks response:

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

Example client code:

```go
// v1 Go client snippet
func ListTasks(ctx context.Context, client *http.Client) ([]TaskV1, error) {
    req, _ := http.NewRequestWithContext(ctx, http.MethodGet, "https://api.example.com/tasks", nil)
    req.Header.Set("X-Auth-Token", os.Getenv("ZRB_API_KEY"))

    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var tasks []TaskV1
    if err := json.NewDecoder(resp.Body).Decode(&tasks); err != nil {
        return nil, err
    }
    return tasks, nil
}
```

### After (v2)

List tasks response envelope:

```json
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v2", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

Example updated client code with cursor handling:

```go
// v2 types

type TaskV2 struct {
    ID        string `json:"id"`
    Title     string `json:"title"`
    Completed bool   `json:"completed"`
    ProjectID string `json:"project_id"`
    CreatedAt string `json:"created_at"`
}

type TaskListResponse struct {
    Items      []TaskV2 `json:"items"`
    Total      int      `json:"total"`
    NextCursor string   `json:"next_cursor"`
}

func ListAllTasks(ctx context.Context, client *http.Client) ([]TaskV2, error) {
    apiToken := os.Getenv("ZRB_API_TOKEN")
    var all []TaskV2
    cursor := ""

    for {
        url := "https://api.example.com/v2/tasks"
        if cursor != "" {
            url += "?cursor=" + url.QueryEscape(cursor)
        }

        req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
        req.Header.Set("Authorization", "Bearer "+apiToken)

        resp, err := client.Do(req)
        if err != nil {
            return nil, err
        }
        defer resp.Body.Close()

        var page TaskListResponse
        if err := json.NewDecoder(resp.Body).Decode(&page); err != nil {
            return nil, err
        }

        all = append(all, page.Items...)

        if page.NextCursor == "" {
            break
        }
        cursor = page.NextCursor
    }

    return all, nil
}
```

If you only care about the first page, you can simply read `items` from the first response and ignore `next_cursor`.

---

## End-to-end before/after example

This section shows a minimal end-to-end flow in v1 and the equivalent in v2.

### v1: create, list, complete, delete

```bash
# Create task
curl -X POST https://api.example.com/tasks \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write migration guide"}'

# List tasks
curl -X GET https://api.example.com/tasks \
  -H "X-Auth-Token: $ZRB_API_KEY"

# Mark task as done (id is an integer)
curl -X PUT https://api.example.com/tasks/42 \
  -H "X-Auth-Token: $ZRB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"done": true}'

# Delete task
curl -X DELETE https://api.example.com/tasks/42 \
  -H "X-Auth-Token: $ZRB_API_KEY"
```

### v2: create, list, complete, delete

```bash
# Create task (requires project_id)
curl -X POST https://api.example.com/v2/tasks \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write migration guide", "project_id": "proj_abc123"}'

# List tasks (paginated envelope)
curl -X GET "https://api.example.com/v2/tasks?limit=20" \
  -H "Authorization: Bearer $ZRB_API_TOKEN"

# Mark task as completed (id is a UUID string)
curl -X PUT https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer $ZRB_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'

# Delete task
curl -X DELETE https://api.example.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer $ZRB_API_TOKEN"
```

---

## Migration checklist

Use this checklist to migrate an existing v1 integration to v2 safely:

1. Authentication
   - [ ] Replace all uses of `X-Auth-Token` with `Authorization: Bearer <token>`
   - [ ] Rotate or provision v2-compatible API tokens if necessary

2. Endpoint paths
   - [ ] Update all hard-coded URLs from `/tasks` to `/v2/tasks`
   - [ ] Update all resource URLs from `/tasks/{id}` to `/v2/tasks/{id}`

3. Data types and models
   - [ ] Change `Task.id` type from integer to string/UUID in your models and type definitions
   - [ ] Rename `done` → `completed` everywhere (models, DTOs, serializers, UI bindings)
   - [ ] Add `project_id` to your Task model and ensure it is treated as required on creation

4. Persistence and storage
   - [ ] If you persist task IDs, migrate storage from integer to string/UUID-compatible types
   - [ ] Backfill or configure `project_id` for any logic that creates tasks

5. Request/response handling
   - [ ] Update task creation calls to include a valid `project_id`
   - [ ] Update update calls to send `completed` instead of `done`
   - [ ] Adjust list responses to read from `response.items` instead of a top-level array
   - [ ] (Optional) Implement cursor-based pagination using `next_cursor` and the `cursor` query parameter

6. Testing and rollout
   - [ ] Add/adjust unit tests to cover v2 request/response shapes
   - [ ] Run integration tests against a v2 environment
   - [ ] Verify error handling for missing `project_id`, invalid auth headers, and malformed UUIDs
   - [ ] Deploy changes behind a feature flag or configuration toggle if you need a phased rollout

---

## Upgrade command

Run the following to upgrade your Zrb CLI to v2:

```bash
zrb upgrade --to v2
```
