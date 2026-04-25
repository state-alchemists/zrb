# Zrb CLI v2 Migration Guide

This guide walks you through migrating from Zrb CLI v1 to v2. All examples assume Node.js/JavaScript, but principles apply universally.

---

## Breaking Changes

### 1. CLI Command Prefix

All CLI commands now require the `v2:` prefix.

**v1:**
```bash
zrb task list
zrb task create --title "Do laundry"
zrb task update 42 --done
zrb task delete 42
```

**v2:**
```bash
zrb v2:task list
zrb v2:task create --title "Do laundry"
zrb v2:task update --id a1b2c3d4-e5f6-7890-abcd-ef1234567890 --done
zrb v2:task delete --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### 2. Authentication Header

The authentication header has changed from `X-Auth-Token` to Bearer token.

**v1:**
```bash
curl -H "X-Auth-Token: your_api_key" https://api.zrb.io/tasks
```

**v2:**
```bash
curl -H "Authorization: Bearer your_api_token" https://api.zrb.io/v2/tasks
```

---

### 3. Task ID Type

Task IDs are now UUID strings instead of integers.

**v1:**
```json
{
  "id": 42,
  "title": "Write tests"
}
```

**v2:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests"
}
```

---

### 4. Field Rename: `done` → `completed`

The boolean flag has been renamed.

**v1:**
```json
{
  "id": 42,
  "title": "Ship v1",
  "done": true
}
```

**v2:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Ship v1",
  "completed": true
}
```

---

### 5. Required `project_id` on Task Creation

Creating tasks now requires specifying a project.

**v1:**
```bash
zrb task create --title "New task"
```

**v2:**
```bash
zrb task create --title "New task" --project-id proj_abc123
```

---

### 6. Paginated List Response

List endpoints now return a paginated envelope.

**v1 response:**
```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**v2 response:**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false},
    {"id": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "title": "Ship v1", "completed": true}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

---

## Migration Checklist

1. [ ] Update CLI calls to use `v2:` prefix (e.g., `zrb v2:task list`)
2. [ ] Switch authentication from `X-Auth-Token` to `Authorization: Bearer`
3. [ ] Replace task `id` handling to expect UUID strings (not integers)
4. [ ] Rename all `done` references to `completed` in your code
5. [ ] Include `project_id` when creating new tasks
6. [ ] Implement pagination handling for list endpoints:
   - Extract `items` from the response envelope
   - Use `next_cursor` for subsequent pages
   - Handle empty `next_cursor` as end of pagination

---

## Upgrade Command

Run this command to update your Zrb CLI to v2:

```bash
npm install -g zrb@v2
```

Or with Homebrew:

```bash
brew upgrade zrb
```
