# Zrb CLI v1 to v2 Migration Guide

This guide details the breaking changes and necessary steps to migrate your existing Zrb CLI v1 integrations to v2. Version 2 introduces significant improvements, including project support, enhanced authentication, and consistent pagination.

## Table of Contents

1.  [Endpoint Prefix Change](#endpoint-prefix-change)
2.  [Authentication Header Update](#authentication-header-update)
3.  [Task ID Type Change](#task-id-type-change)
4.  [Task `done` Field Renamed to `completed`](#task-done-field-renamed-to-completed)
5.  [Project ID Requirement for Task Creation](#project-id-requirement-for-task-creation)
6.  [Paginated List Responses](#paginated-list-responses)
7.  [Migration Checklist](#migration-checklist)
8.  [Upgrade Command](#upgrade-command)

---

## 1. Endpoint Prefix Change

All API endpoints now include a `/v2/` prefix.

**Breaking Change:** Direct calls to `/tasks` will no longer work; you must update your URLs.

**Before v1:**

```http
GET /tasks
```

**After v2:**

```http
GET /v2/tasks
```

## 2. Authentication Header Update

The authentication header has changed from `X-Auth-Token` to a standard `Authorization: Bearer` token.

**Breaking Change:** Requests using `X-Auth-Token` will result in an HTTP 401 Unauthorized error.

**Before v1:**

```http
X-Auth-Token: <your_api_key>
```

**After v2:**

```http
Authorization: Bearer <your_api_token>
```

## 3. Task ID Type Change

The `id` field for Task objects has changed from an integer to a UUID string.

**Breaking Change:** Any code that expects or processes task IDs as integers will need to be updated to handle UUID strings.

**Before v1 (Task Object):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After v2 (Task Object):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

## 4. Task `done` Field Renamed to `completed`

The boolean field indicating task completion has been renamed from `done` to `completed`.

**Breaking Change:** References to the `done` field in your code will need to be updated to `completed`.

**Before v1 (Update Task Request Body):**

```json
{
  "title": "Updated title",
  "done": true
}
```

**After v2 (Update Task Request Body):**

```json
{
  "title": "Updated title",
  "completed": true
}
```

## 5. Project ID Requirement for Task Creation

Creating a new task now requires a `project_id`.

**Breaking Change:** Omitting `project_id` in a task creation request will result in an HTTP 422 Unprocessable Entity error.

**Before v1 (Create Task Request Body):**

```json
{
  "title": "New task title"
}
```

**After v2 (Create Task Request Body):**

```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

## 6. Paginated List Responses

All list endpoints (e.g., `GET /v2/tasks`) now return a paginated envelope instead of a bare array of items.

**Breaking Change:** Your code will need to be updated to access task items from the `items` array within the response envelope and handle pagination using `next_cursor`.

**Before v1 (List Tasks Response):**

```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After v2 (List Tasks Response):**

```json
{
  "items": [
    {"id": "...", "title": "Buy milk", "completed": false, "project_id": "...", "created_at": "..."},
    {"id": "...", "title": "Ship v1", "completed": true, "project_id": "...", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

## Migration Checklist

1.  [ ] Update all endpoint URLs to include the `/v2/` prefix.
2.  [ ] Change authentication header from `X-Auth-Token` to `Authorization: Bearer`.
3.  [ ] Modify code to handle Task `id` as a UUID string instead of an integer.
4.  [ ] Replace all occurrences of the `done` field with `completed` in Task objects and requests.
5.  [ ] Ensure all `POST /v2/tasks` requests include a `project_id` in the request body.
6.  [ ] Adjust code that consumes list endpoint responses to extract items from the `items` array and handle `next_cursor` for pagination.

---

## Upgrade Command

To upgrade your Zrb CLI installation:

```bash
zrb upgrade --version 2
```