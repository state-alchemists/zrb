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

The `Task` class is the workhorse for running custom Python code within your Zrb workflows. It is an alias for the foundational `BaseTask` class.

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

### Command with Input and Templating

You can inject context variables directly into the command string using `{ }` syntax.

```python
from zrb import CmdTask, StrInput, cli

figlet_task = cli.add_task(
    CmdTask(
        name="figlet",
        input=StrInput("message", description="Message to display", default="Hello"),
        cmd="figlet '{ctx.input.message}'"
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
        env=[Env(name="API_KEY", is_secret=True)],  # Will prompt if not in OS
        # The curl command can access $API_KEY directly from the shell environment
        cmd='curl -H "Authorization: Bearer $API_KEY" https://api.example.com/data'
    )
)
```

### Background Processes

If you are running a long-lived server, you can background it in bash using `&`, but it's often better to pair it with a [Readiness Check](./readiness-checks.md).

```python
start_server = CmdTask(
    name="start-server",
    cmd="python -m http.server 8000 &"  # Runs in background
)
```

---

## Quick Comparison

| Feature | `Task` | `CmdTask` |
|---------|--------|-----------|
| **Purpose** | Python code | Shell commands |
| **Syntax** | `action=lambda ctx: ...` | `cmd="shell command"` |
| **Templating** | Python string formatting | Jinja2 `{ctx.input.x}` |
| **Return value** | Explicit `return` | stdout captured to XCom |
| **Environment** | Via `os.environ` | Auto-injected into shell |
| **Best for** | Complex logic, APIs | External tools, scripts |

---