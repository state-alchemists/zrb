# Zrb CLI v2 Migration Guide

## Introduction
This guide outlines the breaking changes when upgrading from Zrb CLI v1 to v2, providing detailed instructions and examples for developers to transition smoothly.

## Breaking Changes

### Endpoint Prefix
- **Change:** All endpoints now require the `/v2/` prefix.
  - **v1 Example:**
    ```http
    GET /tasks
    ```
  - **v2 Example:**
    ```http
    GET /v2/tasks
    ```

### Authentication Header
- **Change:** Authentication header changed from `X-Auth-Token` to Bearer token.
  - **v1 Example:**
    ```http
    X-Auth-Token: <your_api_key>
    ```
  - **v2 Example:**
    ```http
    Authorization: Bearer <your_api_token>
    ```

### Task ID Format
- **Change:** Task `id` type changed from integer to UUID string.
  - **v1 Example:**
    ```json
    {
      "id": 42,
      "title": "Write tests",
      "done": false
    }
    ```
  - **v2 Example:**
    ```json
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Write tests",
      "completed": false
    }
    ```

### Field Name Change
- **Change:** Task field `done` renamed to `completed`.
  - **v1 Example:**
    ```json
    {
      "done": true
    }
    ```
  - **v2 Example:**
    ```json
    {
      "completed": true
    }
    ```

### New Required Field for Task Creation
- **Change:** Task creation now requires `project_id`.
  - **v1 Example:**
    ```json
    {
      "title": "New task title"
    }
    ```
  - **v2 Example:**
    ```json
    {
      "title": "New task title",
      "project_id": "proj_abc123"
    }
    ```

### Pagination
- **Change:** List endpoints return a paginated envelope instead of a bare array.
  - **v1 Example:**
    ```json
    [
      {"id": 1, "title": "Buy milk", "done": false},
      {"id": 2, "title": "Ship v1", "done": true}
    ]
    ```
  - **v2 Example:**
    ```json
    {
      "items": [
        {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Buy milk", "completed": false}
      ],
      "total": 2,
      "next_cursor": null
    }
    ```

## Migration Checklist
1. **Update Endpoints**: Add `/v2/` prefix to all API calls.
2. **Adjust Authentication**: Change to the Bearer token system.
3. **Refactor Task IDs**: Rewrite logic to use UUID strings for task IDs.
4. **Rename Fields**: Replace any usage of `done` with `completed`.
5. **Include Project ID**: Ensure `project_id` is included in task creation requests.
6. **Implement Pagination**: Adjust logic to handle the paginated response structure.

## Upgrade Command
To upgrade to v2, use the following command:
```bash
zrb upgrade --version 2
```

Following this guide will help ensure your transition to Zrb CLI v2 is as seamless as possible. Should you face any issues, refer to the detailed examples above or consult our support team.
