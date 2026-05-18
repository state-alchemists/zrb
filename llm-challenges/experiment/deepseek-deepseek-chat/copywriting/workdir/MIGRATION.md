# Zrb CLI v1 → v2 Migration Guide

**Audience:** Developers currently using Zrb CLI v1
**Target version:** v2
**Upgrade command:** `pip install --upgrade zrb-cli`

---

## Table of Contents

1. [Overview](#overview)
2. [Breaking Change 1 — Endpoint Prefix](#breaking-change-1--endpoint-prefix)
3. [Breaking Change 2 — Authentication Header](#breaking-change-2--authentication-header)
4. [Breaking Change 3 — Task ID Type](#breaking-change-3--task-id-type)
5. [Breaking Change 4 — Field Rename: `done` → `completed`](#breaking-change-4--field-rename-done--completed)
6. [Breaking Change 5 — `project_id` Required on Create](#breaking-change-5--project_id-required-on-create)
7. [Breaking Change 6 — Paginated List Envelope](#breaking-change-6--paginated-list-envelope)
8. [Migration Checklist](#migration-checklist)
9. [Upgrade Command](#upgrade-command)

---

## Overview

Zrb CLI v2 introduces projects, stricter authentication, pagination, and consistent ID types. Every change and the rationale is documented below.

There are **6 breaking changes** — each is self-contained, so you can migrate incrementally.

---

## Breaking Change 1 — Endpoint Prefix

All endpoints now live under `/v2/`. Requests to the bare `/tasks` endpoints will fail.

**Before (v1):**

```bash
curl https://api.zrb.dev/tasks
curl https://api.zrb.dev/tasks/42
curl -X POST https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl https://api.zrb.dev/v2/tasks
curl https://api.zrb.dev/v2/tasks/42
curl -X POST https://api.zrb.dev/v2/tasks
```

**Error on mismatch:** Requests to unversioned endpoints will receive HTTP 404 or 410.

---

## Breaking Change 2 — Authentication Header

The authentication header has changed from `X-Auth-Token` to a standard Bearer token in the `Authorization` header. Using the old header returns HTTP 401.

**Before (v1):**

```bash
curl -H "X-Auth-Token: abc123" https://api.zrb.dev/tasks
```

**After (v2):**

```bash
curl -H "Authorization: Bearer abc123" https://api.zrb.dev/v2/tasks
```

**Why:** The standard `Authorization: Bearer` header improves interoperability with API gateways, OAuth flows, and tooling that expects this convention.

---

## Breaking Change 3 — Task ID Type

Task IDs are now UUID strings instead of integers. Any code that stores, compares, or constructs task IDs must be updated.

**Before (v1):**

```json
{
  "id": 42,
  "title": "Write tests",
  "done": false
}
```

**After (v2):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Write tests",
  "completed": false
}
```

**Impact areas:**

- Hard-coded task IDs (e.g., in test fixtures, scripts)
- URL construction (e.g., `/v2/tasks/42` → `/v2/tasks/a1b2c3d4-...`)
- Client-side ID comparisons and caching
- Database foreign keys that reference task IDs

**Note:** V1 integer IDs are not reused. You cannot construct v2 UUIDs from v1 integers. Fetch the new UUID by migrating existing tasks through a data snapshot.

---

## Breaking Change 4 — Field Rename: `done` → `completed`

The boolean task field is now `completed` instead of `done`. This affects reads and writes.

**Before (v1) — Create/Update request:**

```json
{
  "title": "Write tests",
  "done": true
}
```

**After (v2) — Create/Update request:**

```json
{
  "title": "Write tests",
  "completed": true
}
```

**Before (v1) — Response handling:**

```javascript
const task = await response.json();
if (task.done) {
  console.log("Task is finished");
}
```

**After (v2) — Response handling:**

```javascript
const task = await response.json();
if (task.completed) {
  console.log("Task is finished");
}
```

**Why:** `completed` is more explicit and aligns with common project management terminology (e.g., completion rate, incomplete items).

---

## Breaking Change 5 — `project_id` Required on Create

Creating a task now requires a `project_id` string. Omit it and you receive HTTP 422.

**Before (v1):**

```bash
curl -X POST https://api.zrb.dev/tasks \
  -H "X-Auth-Token: abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task"}'
```

**After (v2):**

```bash
curl -X POST https://api.zrb.dev/v2/tasks \
  -H "Authorization: Bearer abc123" \
  -H "Content-Type: application/json" \
  -d '{"title": "New task", "project_id": "proj_abc123"}'
```

**Migration tip:** If you currently have a flat task list, create a single "General" project in v2 (e.g., `proj_default`) and assign all existing tasks to it.

---

## Breaking Change 6 — Paginated List Envelope

List endpoints no longer return a bare array. They return a paginated envelope with `items`, `total`, and `next_cursor`.

**Before (v1):**

```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Ship v1", "done": true}
]
```

**After (v2):**

```json
{
  "items": [
    {"id": "a1b2...", "title": "Buy milk", "completed": false},
    {"id": "c3d4...", "title": "Ship v2", "completed": true}
  ],
  "total": 42,
  "next_cursor": "cursor_xyz"
}
```

**Client code migration — Before (v1):**

```javascript
const tasks = await response.json();
tasks.forEach(task => console.log(task.title));
```

**Client code migration — After (v2):**

```javascript
const body = await response.json();
const tasks = body.items;
const total = body.total;
const nextCursor = body.next_cursor;

tasks.forEach(task => console.log(task.title));

// To fetch the next page:
if (nextCursor) {
  const nextUrl = `/v2/tasks?cursor=${nextCursor}&limit=20`;
  // ...
}
```

**Default page size:** 20 items. Pass `?limit=<N>` to adjust (max 100).

**Why:** A paginated envelope prevents memory exhaustion for large collections and provides a stable cursor-based pagination scheme that works correctly under concurrent writes.

---

## Migration Checklist

Use this checklist to track your migration progress:

- [ ] **1. Update base URLs** — Replace all `https://api.zrb.dev/tasks` with `https://api.zrb.dev/v2/tasks`.
- [ ] **2. Update authentication headers** — Replace `X-Auth-Token` with `Authorization: Bearer <token>`.
- [ ] **3. Migrate task IDs** — Update any code that stores, compares, or constructs integer IDs to use UUID strings.
- [ ] **4. Rename `done` to `completed`** — Update all request bodies, response handlers, and local data models.
- [ ] **5. Add `project_id` to Create Task calls** — Obtain a project ID from the v2 API and include it.
- [ ] **6. Update list response handling** — Read from `body.items` instead of the response body directly. Add pagination logic if fetching beyond the first page.
- [ ] **7. Update test fixtures** — Ensure all test data reflects the new shapes and types.
- [ ] **8. Run integration tests** — Verify all CRUD flows pass against the v2 API.
- [ ] **9. Update client SDK / type definitions** — If you maintain a wrapper library or TypeScript types, update them to match the v2 schema.

---

## Upgrade Command

Once the checklist items above are addressed in your code, upgrade your Zrb CLI installation:

```bash
pip install --upgrade zrb-cli
```

Verify the installed version:

```bash
zrb --version
# Expected output: zrb-cli v2.x.x
```

All v1 endpoints will remain available for a deprecation window of 6 months from the v2 release date, but they will not receive bug fixes or security patches. We recommend completing your migration as soon as possible.
