# Zrb CLI v1 to v2 Migration Guide

This guide outlines the breaking changes introduced in Zrb CLI v2 and provides a clear path for migrating your existing v1 integrations. Version 2 brings significant improvements, including project support, enhanced authentication, and consistent pagination.

## Table of Contents
1.  [Introduction](#introduction)
2.  [Breaking Changes](#breaking-changes)
    1.  [All Endpoints Now Prefixed with `/v2/`](#all-endpoints-now-prefixed-with-v2)
    2.  [Authentication Header Changed](#authentication-header-changed)
    3.  [Task `id` Type Changed from Integer to UUID String](#task-id-type-changed-from-integer-to-uuid-string)
    4.  [Task Field `done` Renamed to `completed`](#task-field-done-renamed-to-completed)
    5.  [Task Creation Now Requires `project_id`](#task-creation-now-requires-project_id)
    6.  [List Endpoints Return a Paginated Envelope](#list-endpoints-return-a-paginated-envelope)
3.  [Migration Checklist](#migration-checklist)
4.  [Upgrade Command](#upgrade-command)

## Introduction

Zrb CLI v2 introduces several breaking changes to improve API consistency, security, and scalability. This guide is designed for experienced developers currently using v1 to help them transition smoothly to v2. Please review all changes carefully before upgrading.

## Breaking Changes

### 1. All Endpoints Now Prefixed with `/v2/`

All API endpoints now require a `/v2/` prefix. Requests to v1 endpoints (without `/v2/`) will no longer be supported.

**Before (v1):**
```bash
curl -X GET https://api.zrb.com/tasks \
     -H "X-Auth-Token: <your_api_key>"
```

**After (v2):**
```bash
curl -X GET https://api.zrb.com/v2/tasks \
     -H "Authorization: Bearer <your_api_token>"
```

### 2. Authentication Header Changed

The authentication mechanism has been updated for enhanced security. The `X-Auth-Token` header is no longer accepted. All requests must now use a Bearer token in the `Authorization` header.

**Before (v1):**
```http
X-Auth-Token: <your_api_key>
```

**After (v2):**
```http
Authorization: Bearer <your_api_token>
```

Requests using the old `X-Auth-Token` header will receive an HTTP 401 Unauthorized response.

### 3. Task `id` Type Changed from Integer to UUID String

The `id` field for Task objects has changed from an auto-assigned integer to a UUID string. This affects how you reference tasks in `GET`, `PUT`, and `DELETE` requests, as well as how you store and handle task identifiers.

**Before (v1 - Task Object):**
```json
{
  "id": 42,
  "title": "Write tests",
  "done": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**After (v2 - Task Object):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false,
  "project_id": "proj_abc123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Example (Get Task):**

**Before (v1):**
```bash
curl -X GET https://api.zrb.com/tasks/42 \
     -H "X-Auth-Token: <your_api_key>"
```

**After (v2):**
```bash
curl -X GET https://api.zrb.com/v2/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
     -H "Authorization: Bearer <your_api_token>"
```

### 4. Task Field `done` Renamed to `completed`

The boolean field indicating a task's completion status has been renamed from `done` to `completed`. This change affects requests where you set or check task status.

**Before (v1 - Update Task Request Body):**
```json
{
  "title": "Updated title",
  "done": true
}
```

**After (v2 - Update Task Request Body):**
```json
{
  "title": "Updated title",
  "completed": true
}
```

### 5. Task Creation Now Requires `project_id`

Tasks are now organized within projects. When creating a new task, the `project_id` field is now mandatory in the request body. Omitting `project_id` will result in an HTTP 422 Unprocessable Entity error.

**Before (v1 - Create Task Request Body):**
```json
{
  "title": "New task title"
}
```

**After (v2 - Create Task Request Body):**
```json
{
  "title": "New task title",
  "project_id": "proj_abc123"
}
```

### 6. List Endpoints Return a Paginated Envelope

All list endpoints (e.g., `GET /v2/tasks`) now return a paginated envelope object instead of a bare array of items. This new structure includes `items`, `total`, and `next_cursor` fields to facilitate efficient pagination.

**Before (v1 - List Tasks Response):**
```json
[
  {"id": 1, "title": "Buy milk", "done": false, "created_at": "..."},
  {"id": 2, "title": "Ship v1", "done": true, "created_at": "..."}
]
```

**After (v2 - List Tasks Response):**
```json
{
  "items": [
    {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false, "project_id": "proj_abc123", "created_at": "..."},
    {"id": "b1c2d3e4-f5a6-7890-bcde-f12345678901", "title": "Ship v2", "completed": true, "project_id": "proj_abc123", "created_at": "..."}
  ],
  "total": 2,
  "next_cursor": "cursor_xyz"
}
```

To fetch subsequent pages, include the `cursor` query parameter with the `next_cursor` value from the previous response:
`GET /v2/tasks?cursor=cursor_xyz`

## Migration Checklist

To successfully migrate your Zrb CLI integrations from v1 to v2, follow these steps:

1.  [ ] **Update CLI version:** Upgrade your Zrb CLI installation to v2.
2.  [ ] **Review authentication:** Change all API requests to use `Authorization: Bearer <your_api_token>` header instead of `X-Auth-Token`.
3.  [ ] **Adjust endpoint paths:** Prefix all Zrb API endpoint URLs with `/v2/`.
4.  [ ] **Handle Task IDs:** Update your code to expect and handle UUID strings for task `id`s instead of integers. Ensure any storage or parsing logic is updated.
5.  [ ] **Rename `done` to `completed`:** Replace all occurrences of the `done` field with `completed` in your request bodies and response parsing logic.
6.  [ ] **Add `project_id` to Task creation:** Modify your task creation requests to include a mandatory `project_id` in the request body.
7.  [ ] **Adapt to paginated list responses:** Update your code that consumes list endpoints to parse the new paginated envelope structure (checking for `items`, `total`, and `next_cursor`). Implement logic to handle pagination using the `cursor` query parameter.
8.  [ ] **Test thoroughly:** After making the necessary changes, perform comprehensive testing of your application to ensure all integrations with the Zrb CLI are functioning correctly with v2.

## Upgrade Command

To upgrade your Zrb CLI, run:

```bash
zrb upgrade --version 2.0
```
