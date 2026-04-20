We're building a project management API. The scaffolding is in `app/`. Several features are missing or incomplete:

1. **Authentication** (`app/auth.py`): The `require_api_key` dependency exists but does nothing. Implement it: read the `X-API-Key` header, validate it against `VALID_API_KEYS` in `database.py`, and raise HTTP 401 if missing or invalid.

2. **Task filtering** (`GET /tasks`): Add optional query parameters: `status`, `priority`, `assigned_to`. Return only matching tasks. All filters are optional and combinable.

3. **Pagination** (`GET /tasks`): Add `page` (default 1) and `page_size` (default 20) query params. Return only the matching slice.

4. **Create task** (`POST /tasks`): Implement this endpoint. It must:
   - Require authentication (use `require_api_key`)
   - Validate that `project_id` exists; return HTTP 404 if not
   - Auto-generate a unique integer ID
   - Return the created task

5. **Update task** (`PUT /tasks/{task_id}`): Allow partial updates to `title`, `status`, `priority`, `assigned_to`. Require auth. Return 404 if not found.

6. **Delete task** (`DELETE /tasks/{task_id}`): Require auth. Return 404 if not found.

Follow the existing patterns in `app/main.py`.
