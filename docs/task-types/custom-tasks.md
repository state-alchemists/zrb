🔖 [Documentation Home](../../README.md) > [Task Types](./) > Custom Tasks

# Custom Task Types (Subclassing `BaseTask`)

When `Task`, `CmdTask`, or `@make_task` aren't enough — because you need reusable task logic with internal state, custom lifecycle hooks, or async initialization — you can subclass `BaseTask`.

---

## Table of Contents

- [When to Subclass](#when-to-subclass)
- [Minimal Subclass](#minimal-subclass)
- [The `run` Method](#the-run-method)
- [Async Tasks](#async-tasks)
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

The simplest custom task requires just a `name` and a `run` method:

```python
from zrb import BaseTask, cli

class GreetTask(BaseTask):
    def run(self, ctx):
        ctx.print(f"Hello from {self.name}!")

cli.add_task(GreetTask(name="greet"))
```

```bash
zrb greet
# Output: Hello from greet!
```

> **Note:** `Task` is an alias for `BaseTask`. You can subclass either one.

---

## The `run` Method

The `run` method is the task's entry point. It receives `ctx` (the task context) and can return a value for XCom:

```python
class ComputeTask(BaseTask):
    def run(self, ctx):
        result = self._compute(ctx)
        ctx.print(f"Result: {result}")
        return result  # Auto-pushed to XCom

    def _compute(self, ctx):
        # Internal helper — not a lifecycle method
        return ctx.input.base * 2
```

---

## Async Tasks

For I/O-bound operations, override `async_run` instead of `run`:

```python
import asyncio
from zrb import BaseTask, cli

class AsyncComputeTask(BaseTask):
    async def async_run(self, ctx):
        ctx.print("Starting async computation...")
        await asyncio.sleep(1)
        result = 42
        ctx.print(f"Async result: {result}")
        return result
```

> **How it works:** `BaseTask.run()` wraps the synchronous call. `BaseTask.async_run()` is the async entry point. If you override `run`, it will be called from within a synchronous wrapper. Override `async_run` for true async execution.

### Retry Behavior with Async Tasks

Async tasks participate in the same retry mechanism:

```python
class FlakyTask(BaseTask):
    def __init__(self, **kwargs):
        super().__init__(retries=3, retry_period=1.0, **kwargs)

    async def async_run(self, ctx):
        # This will be retried up to 3 times on failure
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
| `run(ctx)` | Task execution (sync) | Main synchronous action |
| `async_run(ctx)` | Task execution (async) | Main async action |
| `get_task_status(session)` | Status resolution | Custom status logic |

### Example: Custom Task with Init-Time Setup

```python
class DatabaseTask(BaseTask):
    def __init__(self, connection_string: str = "", **kwargs):
        # Pass all standard params to BaseTask
        super().__init__(**kwargs)
        # Store custom params
        self._connection_string = connection_string

    def run(self, ctx):
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

    def run(self, ctx):
        import httpx
        response = httpx.request(
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

2. **Use `async_run` for I/O.** If your task makes network calls, file I/O, or waits on external services, override `async_run`.

3. **Document custom parameters.** If you add constructor parameters, include docstrings so they appear in IDE tooltips.

4. **Match existing patterns.** Look at built-in tasks like `CmdTask`, `HttpCheck`, or `Scaffolder` for reference implementations.

5. **Prefer composition over deep inheritance.** If you find yourself creating 3+ levels of subclassing, consider composing with `upstream` and `successor` instead.

---

## Quick Reference

```python
from zrb import BaseTask, cli

# Sync subclass
class MyTask(BaseTask):
    def run(self, ctx):
        ctx.print("Doing work")
        return "result"

# Async subclass
class MyAsyncTask(BaseTask):
    async def async_run(self, ctx):
        await some_io()
        return "result"

# Subclass with custom params
class MyCustomTask(BaseTask):
    def __init__(self, custom_param: str, **kwargs):
        super().__init__(**kwargs)
        self._custom = custom_param

    def run(self, ctx):
        ctx.print(f"Param: {self._custom}")

# Register like any task
cli.add_task(MyTask(name="my-task"))
```
