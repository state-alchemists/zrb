# Zrb Task API — v1 Reference

## Authentication

All requests require an API key passed in the header:

```
X-Auth-Token: <your_api_key>
```

## Data Types

### Task Object

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

- `id` — integer, auto-assigned
- `title` — string
- `done` — boolean, default `false`
- `created_at` — ISO 8601 timestamp

## Endpoints

### List Tasks

`GET /tasks`

Returns a bare array of task objects.

**Response:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

### Get Task

`GET /tasks/{id}`

Returns a single task or `404`.

### Create Task

`POST /tasks`

**Request body:**
```json
{
  "title": "New task title"
}
```

**Response:** the created task object (HTTP 201).

### Update Task

`PUT /tasks/{id}`

**Request body** (all fields optional):
```json
{
  "title": "Updated title",
  "done": true
}
```

**Response:** the updated task object.

### Delete Task

`DELETE /tasks/{id}`

**Response:** HTTP 204 No Content.
