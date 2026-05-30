🔖 [Documentation Home](../../README.md) > [Task Types](./) > Custom Tasks

# Custom Task Types (Subclassing `BaseTask`)

When `Task`, `CmdTask`, or `@make_task` aren't enough — because you need reusable task logic with internal state, custom lifecycle hooks, or async initialization — you can subclass `BaseTask`.

---

## Table of Contents

- [When to Subclass](#when-to-subclass)
- [Minimal Subclass](#minimal-subclass)
- [The `_exec_action` Method](#the-_exec_action-method)
- [Retry Behavior](#retry-behavior)
- [Full Lifecycle Hooks](#full-lifecycle-hooks)
- [Reusable Task with Configuration](#reusable-task-with-configuration)
- [Best Practices](#best-practices)

---

## When to Subclass

| Approach | Use Case |
|----------|----------|
| `@make_task` | Single-use tasks, simple logic |
| `Task(action=lambda ...)` | Quick inline tasks |
| **Subclass `BaseTask`** | Reusable task types, custom lifecycle, shared state across runs |

---

## Minimal Subclass

The simplest custom task requires just a `name` and an `_exec_action` coroutine:

```python
from zrb import BaseTask, cli
from zrb.context.any_context import AnyContext

class GreetTask(BaseTask):
    async def _exec_action(self, ctx: AnyContext):
        ctx.print(f"Hello from {self.name}!")

cli.add_task(GreetTask(name="greet"))
```

```bash
zrb greet
# Output: Hello from greet!
```

> **Note:** `Task` is an alias for `BaseTask`. You can subclass either one.
>
> ⚠️ **Do not override `run()` or `async_run()`** — those are the synchronous and asynchronous *entry points* used by the CLI and have the signature `(self, session=None, str_kwargs=None, kwargs=None)`. Overriding them would break task invocation. The hook for your custom logic is `_exec_action(self, ctx)`, which all built-in subclasses (`CmdTask`, `HttpCheck`, `Scaffolder`, `Scheduler`, ...) override.

---

## The `_exec_action` Method

`_exec_action` is an **async** method that receives `ctx` (the task context) and returns a value that is automatically pushed to XCom:

```python
class ComputeTask(BaseTask):
    async def _exec_action(self, ctx: AnyContext):
        result = self._compute(ctx)
        ctx.print(f"Result: {result}")
        return result  # Auto-pushed to XCom

    def _compute(self, ctx):
        # Internal helper — not a lifecycle method
        return ctx.input.base * 2
```

For I/O-bound work, just `await` inside `_exec_action`:

```python
import asyncio
from zrb import BaseTask, cli
from zrb.context.any_context import AnyContext

class AsyncComputeTask(BaseTask):
    async def _exec_action(self, ctx: AnyContext):
        ctx.print("Starting async computation...")
        await asyncio.sleep(1)
        result = 42
        ctx.print(f"Async result: {result}")
        return result
```

> **Sync code in `_exec_action`:** Because `_exec_action` is `async`, calling sync code is fine — but blocking calls (heavy I/O, CPU work) will block the event loop and stall sibling tasks. Wrap them in `asyncio.to_thread(...)` or `loop.run_in_executor(...)` if needed.

---

## Retry Behavior

`_exec_action` participates in the same retry mechanism as other tasks. Raise an exception to trigger a retry:

```python
class FlakyTask(BaseTask):
    def __init__(self, **kwargs):
        super().__init__(retries=3, retry_period=1.0, **kwargs)

    async def _exec_action(self, ctx: AnyContext):
        # This will be retried up to 3 additional times on failure
        response = await some_http_call()
        if response.status != 200:
            raise RuntimeError("API failed")
        return response.data
```

---

## Full Lifecycle Hooks

`BaseTask` exposes several methods you can override for finer control:

| Method | When It's Called | Override For |
|--------|-----------------|--------------|
| `__init__` | Task definition time | Setting defaults, custom parameters |
| `_exec_action(ctx)` *(async)* | During task execution | Main action logic — **this is the primary override** |

> **Entry points (don't override):** `run(self, session, str_kwargs, kwargs)` and `async_run(...)` are public entry points used by the CLI to start a task. Their signature is fixed; override `_exec_action` instead.

### Example: Custom Task with Init-Time Setup

```python
from zrb import BaseTask, cli
from zrb.context.any_context import AnyContext

class DatabaseTask(BaseTask):
    def __init__(self, connection_string: str = "", **kwargs):
        # Pass all standard params to BaseTask
        super().__init__(**kwargs)
        # Store custom params
        self._connection_string = connection_string

    async def _exec_action(self, ctx: AnyContext):
        ctx.print(f"Connecting to {self._connection_string}")
        # ... database logic ...

# Usage
db_job = DatabaseTask(
    name="migrate",
    connection_string="postgresql://localhost/mydb",
    upstream=[prepare_task],
    retries=2,
)
cli.add_task(db_job)
```

---

## Reusable Task with Configuration

For task types you'll use across many projects, encapsulate inputs and envs:

```python
from zrb import BaseTask, StrInput, Env

class ApiCallTask(BaseTask):
    def __init__(
        self,
        name: str,
        endpoint: str,
        method: str = "GET",
        **kwargs,
    ):
        # Define standard inputs
        inputs = [
            StrInput(
                name="payload",
                description="JSON payload for the request",
                default="{}",
            ),
        ]
        # Define env vars (prompted if not in OS)
        envs = [
            Env(name="API_KEY", is_secret=True),
        ]
        super().__init__(
            name=name,
            input=inputs,
            env=envs,
            **kwargs,
        )
        self._endpoint = endpoint
        self._method = method

    async def _exec_action(self, ctx):
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=self._method,
                url=self._endpoint,
                headers={"Authorization": f"Bearer {ctx.env.API_KEY}"},
                data=ctx.input.payload,
            )
        return response.json()

# Use it like any built-in task
cli.add_task(ApiCallTask(
    name="get-users",
    endpoint="https://api.example.com/users",
))
```

---

## Best Practices

1. **Accept `**kwargs`** in your `__init__` and pass them to `super().__init__()`. This ensures all standard `BaseTask` parameters (`upstream`, `retries`, `color`, etc.) remain usable.

2. **`_exec_action` is async.** `await` your I/O calls directly. If you have blocking work, hand it to `asyncio.to_thread` so you don't stall the event loop.

3. **Document custom parameters.** If you add constructor parameters, include docstrings so they appear in IDE tooltips.

4. **Match existing patterns.** Look at built-in tasks like `CmdTask` (`src/zrb/task/cmd_task.py`), `HttpCheck`, or `Scaffolder` — they all override `_exec_action`.

5. **Prefer composition over deep inheritance.** If you find yourself creating 3+ levels of subclassing, consider composing with `upstream` and `successor` instead.

---

## Quick Reference

```python
from zrb import BaseTask, cli
from zrb.context.any_context import AnyContext

# Minimal subclass — override _exec_action (always async)
class MyTask(BaseTask):
    async def _exec_action(self, ctx: AnyContext):
        ctx.print("Doing work")
        return "result"

# I/O-bound subclass
class MyAsyncTask(BaseTask):
    async def _exec_action(self, ctx: AnyContext):
        await some_io()
        return "result"

# Subclass with custom params
class MyCustomTask(BaseTask):
    def __init__(self, custom_param: str, **kwargs):
        super().__init__(**kwargs)
        self._custom = custom_param

    async def _exec_action(self, ctx: AnyContext):
        ctx.print(f"Param: {self._custom}")

# Register like any task
cli.add_task(MyTask(name="my-task"))
```
