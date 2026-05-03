🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > The @make_task Decorator

# The `@make_task` Decorator

The `@make_task` decorator is the cleanest, most Pythonic way to define Zrb tasks. It wraps a plain Python function into a full `BaseTask`, handling registration, dependency wiring, and context injection automatically.

---

## Table of Contents

- [Basic Usage](#basic-usage)
- [All Parameters Reference](#all-parameters-reference)
- [Parameter Groups](#parameter-groups)
- [Advanced Patterns](#advanced-patterns)
- [Comparison with Direct Instantiation](#comparison-with-direct-instantiation)

---

## Basic Usage

The decorated function receives a single `ctx` argument (the task's `Context`) and can optionally return a value that is automatically pushed to XCom.

```python
from zrb import make_task, cli

@make_task(name="hello", group=cli)
def say_hello(ctx):
    ctx.print("Hello, World!")
```

```bash
zrb hello
```

---

## All Parameters Reference

```python
@make_task(
    name="my-task",
    color: int | None = None,
    icon: str | None = None,
    description: str | None = None,
    cli_only: bool = False,
    input: list[AnyInput] | AnyInput | None = None,
    env: list[AnyEnv] | AnyEnv | None = None,
    execute_condition: bool | str | Callable = True,
    retries: int = 2,
    retry_period: float = 0,
    readiness_check: list[AnyTask] | AnyTask | None = None,
    readiness_check_delay: float = 0.5,
    readiness_check_period: float = 5,
    readiness_failure_threshold: int = 1,
    readiness_timeout: int = 60,
    monitor_readiness: bool = False,
    upstream: list[AnyTask] | AnyTask | None = None,
    fallback: list[AnyTask] | AnyTask | None = None,
    successor: list[AnyTask] | AnyTask | None = None,
    print_fn: PrintFn | None = None,
    group: AnyGroup | None = None,
    alias: str | None = None,
)
def my_function(ctx):
    ...
```

---

## Parameter Groups

### Identity & Appearance

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | *(required)* | Task name used in CLI (`zrb <name>`) and XCom references |
| `color` | `None` (auto) | ANSI 256-color code (`1`=red, `2`=green, `3`=yellow, `4`=blue) |
| `icon` | `None` | Emoji or string prefix shown in terminal output |
| `description` | `None` | Human-readable description shown in `zrb --help` |
| `cli_only` | `False` | If `True`, task can only be triggered from CLI, not programmatically |

### Data & Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `input` | `None` | List of `AnyInput` objects (see [Inputs](./inputs.md)) |
| `env` | `None` | List of `Env`/`EnvMap`/`EnvFile` for environment injection |

### Execution Control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `execute_condition` | `True` | Boolean, f-string, or callable. If `False`/falsy, task is skipped |
| `retries` | `2` | Number of additional attempts on failure (3 total) |
| `retry_period` | `0` | Seconds to wait between retries |

### Readiness Checks

| Parameter | Default | Description |
|-----------|---------|-------------|
| `readiness_check` | `None` | Task(s) that probe readiness (e.g., HTTP check) |
| `readiness_check_delay` | `0.5` | Initial delay before first check |
| `readiness_check_period` | `5` | Interval between checks (seconds) |
| `readiness_failure_threshold` | `1` | Consecutive failures before declaring unready |
| `readiness_timeout` | `60` | Max total wait time |
| `monitor_readiness` | `False` | Keep checking periodically *after* ready |

### Dependencies & Flow Control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `upstream` | `None` | Task(s) that must complete before this task runs |
| `fallback` | `None` | Task(s) that run only if this task permanently fails |
| `successor` | `None` | Task(s) that run only if this task succeeds |

### Registration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `group` | `None` | CLI group to register the task under (e.g., `cli`, or a `Group` object) |
| `alias` | `None` | Alternative name within the group |

> **Important:** When you pass `group`, the decorator automatically calls `group.add_task(task)`. Without it, you must add the task manually.

---

## Advanced Patterns

### Using `input`, `env`, and `upstream` Together

```python
from zrb import make_task, cli, StrInput, Env

@make_task(
    name="deploy",
    group=cli,
    input=StrInput(name="version", description="Release version"),
    env=Env(name="DEPLOY_KEY", is_secret=True),
    upstream=[build_task, test_task],
    execute_condition=lambda ctx: ctx.env.ENVIRONMENT == "staging",
    retries=1,
)
def do_deploy(ctx):
    ctx.print(f"Deploying version {ctx.input.version}...")
```

### Conditional Execution with Callable

The `execute_condition` parameter accepts a lambda or function that receives `ctx`:

```python
@make_task(
    name="cleanup",
    group=cli,
    execute_condition=lambda ctx: ctx.env.SKIP_CLEANUP.lower() != "true"
)
def do_cleanup(ctx):
    ctx.print("Running cleanup...")
```

### Readiness Check Pattern

Useful when a task starts a server and needs to wait for it:

```python
from zrb import make_task, HttpCheck

@make_task(
    name="start-app",
    group=cli,
    readiness_check=HttpCheck(name="check-app", url="http://localhost:8080/health"),
    readiness_timeout=120,
)
def start_server(ctx):
    ctx.print("Starting application server...")
    # ... start server ...
```

### Return Value → XCom

```python
@make_task(name="compute", group=cli)
def compute_value(ctx):
    result = 42
    ctx.print(f"Computed: {result}")
    return result  # Automatically available via ctx.xcom['compute'].pop()
```

---

## Comparison with Direct Instantiation

| Aspect | `@make_task` | Direct `Task()` |
|--------|-------------|-----------------|
| **Boilerplate** | Minimal — decorator handles registration | Manual `cli.add_task(...)` required |
| **Action** | Decorated function body | `action=lambda ctx: ...` or subclass |
| **Return value** | `return` in function | Same (lambda `return`) |
| **Async actions** | Use `async def` | Pass `action=async_fn` |
| **Reusable task class** | Not suitable | Subclass `BaseTask` |
| **Registration** | `group=` param auto-registers | Must call `cli.add_task()` |

---

> **Tip:** Use `@make_task` for 90% of your tasks. Reserve direct `Task()` instantiation for in-line lambda tasks and subclassing for reusable task types.
