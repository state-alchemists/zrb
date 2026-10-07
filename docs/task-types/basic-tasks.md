🔖 [Documentation Home](../../README.md) > [Task Types](./) > Basic Tasks

# Basic Task Types

Zrb provides two primary building blocks for creating automations: `Task` (for Python code) and `CmdTask` (for shell commands).

---

## Table of Contents

- [`Task` (Python Code)](#1-task-or-basetask)
- [`CmdTask` (Shell Commands)](#2-cmdtask)
- [Quick Comparison](#quick-comparison)

---

## 1. `Task` (or `BaseTask`)

The `Task` class is the workhorse for running custom Python code within your Zrb workflows. It's a plain subclass of the foundational `BaseTask` class, adding nothing on top — you can use either interchangeably.

### When to Use

| Use Case | Example |
|----------|--------|
| Complex calculations | Mathematical transformations |
| Data manipulation | Processing JSON, filtering lists |
| API calls via Python | Using `requests`, `httpx` |
| Custom logic | Any action not fitting a single shell command |

### Using the `@make_task` Decorator (Recommended)

```python
from zrb import make_task, cli, IntInput

@make_task(
    name="perimeter",
    group=cli,
    input=[
        IntInput(name="height"),
        IntInput(name="width"),
    ]
)
def calculate_perimeter(ctx):
    result = 2 * (ctx.input.height + ctx.input.width)
    ctx.print(f"Perimeter is {result}")
    return result  # Automatically pushed to XCom
```

> 📖 **Full Reference:** See the [`@make_task` Decorator Guide](../core-concepts/make-task.md) for all parameters, advanced patterns, and comparison with direct instantiation.

### Using Direct Instantiation with Lambda

```python
from zrb import Task, cli

calculate = cli.add_task(
    Task(
        name="simple-calc",
        action=lambda ctx: ctx.print("Calculating...")
    )
)
```

### Blocking Code Stalls Sibling Tasks

An `action` runs on the event loop, so a plain `def` that blocks holds every other task in the pipeline behind it. Nothing fails — the work still finishes correctly, it just stops overlapping.

```python
import asyncio

from zrb import Task, cli

async def fetch(ctx):
    await asyncio.sleep(1)          # yields: siblings keep running

def fetch_blocking(ctx):
    import requests
    requests.get("https://example.com")   # holds the loop: siblings wait
```

Ten sibling tasks that each wait for a second finish in about a second when the action is `async`, and about ten when it blocks. Make the action `async` and `await` your I/O, or hand blocking work to `asyncio.to_thread` so the loop stays free:

```python
import asyncio

def fetch_blocking(ctx):
    import requests
    return requests.get("https://example.com").text

async def fetch(ctx):
    return await asyncio.to_thread(fetch_blocking, ctx)
```

The same applies to `_exec_action` in a `BaseTask` subclass — see [Custom Tasks](./custom-tasks.md).

---

## 2. `CmdTask`

The `CmdTask` is your go-to tool for running shell commands. It seamlessly integrates Zrb's context (inputs, envs, xcom) directly into the shell execution environment.

### When to Use

| Use Case | Example |
|----------|--------|
| External programs | `docker`, `kubectl`, `git` |
| Build scripts | `make`, `npm run build` |
| System administration | Shell utilities |
| Quick one-liners | `echo`, `cp`, `mv` |

### Simple Command

```python
from zrb import CmdTask, cli

echo_task = cli.add_task(CmdTask(name="echo", cmd="echo 'Hello, World!'"))
```

A multi-line `cmd` (or a list of commands) runs as one shell script, so, as in any shell script, a failing line does not stop the ones after it; the task's exit code is the last command's. Start the script with `set -e` to stop at the first failure.

### Command with Input and Templating

You can inject context variables into the command by wrapping it in `Tpl`, which
renders `{ }` expressions against the task context. A bare string is a literal, so
braces meant for the shell (`${VAR}`, `awk '{print}'`) need no escaping — and a
plain-string `cmd` carrying a `{ctx.` placeholder warns when the task is built,
since it would reach the shell as those characters instead of being rendered.

```python
from zrb import CmdTask, StrInput, Tpl, cli

figlet_task = cli.add_task(
    CmdTask(
        name="figlet",
        input=StrInput("message", description="Message to display", default="Hello"),
        cmd=Tpl("figlet '{ctx.input.message}'")
    )
)
```

### Command with Environment Variables

`CmdTask` automatically injects defined `Env` variables into the OS environment of the subprocess.

```python
from zrb import CmdTask, Env, cli

api_call_task = cli.add_task(
    CmdTask(
        name="api-call",
        env=[Env(name="API_KEY", default="")],  # Reads $API_KEY from the OS, "" if unset
        # The curl command can access $API_KEY directly from the shell environment
        cmd='curl -H "Authorization: Bearer $API_KEY" https://api.example.com/data'
    )
)
```

### Long-Running Processes

Appending `&` does not make a `CmdTask` finish early: the backgrounded process keeps the task's output pipe open, so the task (and `zrb`) waits for it anyway. Run a long-lived server in the foreground and attach a [Readiness Check](./readiness-checks.md), which marks the task ready — and unblocks downstream tasks — as soon as the server responds, while the server keeps running.

```python
from zrb import CmdTask, HttpCheck

start_server = CmdTask(
    name="start-server",
    cmd="python -m http.server 8000",  # Foreground; keeps running until you stop zrb (Ctrl+C)
    readiness_check=HttpCheck(name="check-server", url="http://localhost:8000"),
)
```

---

## Quick Comparison

| Feature | `Task` | `CmdTask` |
|---------|--------|-----------|
| **Purpose** | Python code | Shell commands |
| **Syntax** | `action=lambda ctx: ...` | `cmd="shell command"` |
| **Templating** | Python string formatting | Zrb's own f-string-style substitution, wrapped in `Tpl` (single braces, evaluated with a restricted set of builtins) |
| **Return value** | Explicit `return` | A `CmdResult` pushed to XCom: `.output` (stdout), `.error` (stderr); renders as stdout in templates |
| **Environment** | Via `ctx.env` | Auto-injected into shell (and on `ctx.env`) |
| **Best for** | Complex logic, APIs | External tools, scripts |

---

🔖 [Documentation Home](../../README.md) > [Task Types](./) > Basic Tasks
