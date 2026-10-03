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
    name: str,               # positional or keyword; everything else is keyword-only
    color: int | None = None,
    icon: str | None = None,
    description: str | None = None,
    cli_only: bool = False,
    input: list[AnyInput] | AnyInput | None = None,
    env: list[AnyEnv] | AnyEnv | None = None,
    execute_condition: bool | Tpl | Callable = True,
    retries: int = 2,
    retry_if: Callable[[BaseException], bool] | None = None,
    retry_period: float = 0,
    readiness_check: list[AnyTask] | AnyTask | None = None,
    readiness_check_delay: float | None = None,
    readiness_check_period: float = 5,
    readiness_failure_threshold: int = 1,
    readiness_timeout: float | None = None,
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
| `color` | `None` (auto) | Standard SGR color code (`31`=red, `32`=green, `33`=yellow, `34`=blue, ... `90`-`97` for bright variants). Any value outside this set is silently ignored (no color applied) |
| `icon` | `None` | Emoji or string prefix shown in terminal output |
| `description` | `None` | Human-readable description shown in `zrb --help` |
| `cli_only` | `False` | If `True`, task is hidden from the web UI runner's task listing. It has no effect on CLI vs. programmatic (`.run()`/`.async_run()`) execution — both still work regardless of this flag |

### Data & Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `input` | `None` | List of `AnyInput` objects (see [Inputs](./inputs.md)) |
| `env` | `None` | List of `Env`/`EnvMap`/`EnvFile` for environment injection |

### Execution Control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `execute_condition` | `True` | Boolean, `Tpl` template (rendered, then read as a boolean), or callable taking `ctx`. If `False`/falsy, task is skipped. A bare string is a literal, not a template |
| `retries` | `2` | Number of additional attempts on failure (3 total) |
| `retry_if` | `None` | Predicate called with the exception; a falsy result fails the task immediately instead of retrying. `None` retries every failure |
| `retry_period` | `0` | Seconds to wait between retries |

### Readiness Checks

| Parameter | Default | Description |
|-----------|---------|-------------|
| `readiness_check` | `None` | Task(s) that probe readiness (e.g., HTTP check) |
| `readiness_check_delay` | `None` → 0.5s | Seconds to wait after starting the action before the first check. Unset, it comes from `ZRB_TASK_READINESS_DELAY` (milliseconds, default `500`) |
| `readiness_check_period` | `5` | Seconds between checks while monitoring (`monitor_readiness=True`) |
| `readiness_failure_threshold` | `1` | Consecutive check failures tolerated before the task is declared failed |
| `readiness_timeout` | `None` → 60s | Seconds the readiness checks may take before the task fails. Caps the initial wait **and** each re-check round — see note below |
| `monitor_readiness` | `False` | Keep checking periodically *after* ready, and restart the action if the checks start failing |

> **`readiness_timeout` caps both waits.** Left unset (`None`), it takes its value from the `ZRB_TASK_READINESS_TIMEOUT` environment variable (milliseconds), which defaults to `60000` — so a readiness check that never completes fails the task after 60s instead of hanging the run. Set the parameter per task, or the environment variable to change the default for every task. An explicit `0` (or a negative value) removes the cap, and a check that never returns then waits forever.

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
from zrb import make_task, cli, CmdTask, StrInput, Env

build_task = CmdTask(name="build", cmd="echo build")
test_task = CmdTask(name="test", cmd="echo test")

@make_task(
    name="deploy",
    group=cli,
    input=StrInput(name="version", description="Release version"),
    env=[
        Env(name="DEPLOY_KEY", default=""),
        Env(name="ENVIRONMENT", default="dev"),
    ],
    upstream=[build_task, test_task],
    execute_condition=lambda ctx: ctx.env.ENVIRONMENT == "staging",
    retries=1,
)
def do_deploy(ctx):
    ctx.print(f"Deploying version {ctx.input.version}...")
```

### Conditional Execution with Callable

The `execute_condition` parameter accepts a lambda or function that receives `ctx`. Declare any variable it reads as an `Env` with a default — `ctx.env` also exposes the OS environment, but reading a variable that is set nowhere raises `AttributeError`:

```python
@make_task(
    name="cleanup",
    group=cli,
    env=Env(name="SKIP_CLEANUP", default="false"),
    execute_condition=lambda ctx: ctx.env.SKIP_CLEANUP.lower() != "true"
)
def do_cleanup(ctx):
    ctx.print("Running cleanup...")
```

### Readiness Check Pattern

Useful when a task starts a server and needs to wait for it:

```python
from zrb import make_task, cli, HttpCheck

@make_task(
    name="start-app",
    group=cli,
    readiness_check=HttpCheck(name="check-app", url="http://localhost:8080/health"),
)
def start_server(ctx):
    ctx.print("Starting application server...")
    # ... start server ...
```

The `HttpCheck` retries until the endpoint answers, so `start-app` is held until the server is actually serving — up to the 60s default ceiling, after which the task fails. Raise or lower that ceiling per task with `readiness_timeout=`, or for every task with `ZRB_TASK_READINESS_TIMEOUT` (milliseconds):

```bash
ZRB_TASK_READINESS_TIMEOUT=120000 zrb start-app
```

### Return Value → XCom

```python
@make_task(name="compute", group=cli)
def compute_value(ctx):
    result = 42
    ctx.print(f"Computed: {result}")
    return result  # Downstream tasks read it via ctx.xcom['compute'].pop()
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

🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > The @make_task Decorator
