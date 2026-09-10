🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > Session & Context

# Session, Context, and XCom

To understand how data flows through a Zrb pipeline, you must understand the relationship between a `Session`, a `Context`, and `XCom`.

---

## Table of Contents

- [What's the Difference?](#whats-the-difference)
- [The Context (`ctx`)](#the-context-ctx)
- [XCom (Cross-Communication)](#xcom-cross-communication)
- [Ambient Context](#ambient-context)
- [Quick Reference](#quick-reference)

---

## What's the Difference?

| Concept | Analogy | Purpose |
|---------|---------|--------|
| **Session** | Factory floor | Manages a single workflow run from start to finish |
| **Context** (`ctx`) | Workbench | Contains everything a single task needs |
| **XCom** | Conveyor belt | Allows tasks to pass data to each other |



---

## The Context (`ctx`)

When a task executes its `action`, Zrb passes it a `Context` object, universally referred to as `ctx`.

### Shared Data Plane

| Attribute | Description |
|-----------|-------------|
| `ctx.input` | Access parsed user inputs, aggregated from the task and all its upstreams |
| `ctx.env` | Access resolved environment variables, aggregated from the task and all its upstreams |
| `ctx.xcom` | Access the data-sharing queues — this is a single dict shared by the whole session, not filtered by `upstream`. Any task can read any other task's queue as long as that task has run (or is running) in the same session |

### Task-Specific Utilities

| Method | Description |
|--------|-------------|
| `ctx.print(*values)` | Formatted printing (includes task's color and name) |
| `ctx.log_info(msg)` | Log info message to session log |
| `ctx.log_error(msg)` | Log error message to session log |
| `ctx.render(template)` | Render an f-string-style template (single `{}`, evaluated against `ctx` and helpers) |

### Example

```python
from zrb import make_task, cli, StrInput

@make_task(name="context-demo", group=cli, input=StrInput(name="user", default="Zrb"))
def demo(ctx):
    # Logging
    ctx.log_info("Task started")
    
    # Rendering
    rendered = ctx.render("Hello {ctx.input.user}!")
    
    # Printing
    ctx.print(rendered)
```

### Rendering is opt-in

`ctx.render()` above is an explicit call, so it always renders. Task *attributes*
work the other way round: a bare `str` is a **literal** and is never rendered, so
braces meant for the shell (`${VAR}`, `awk '{print}'`) pass through untouched.
Wrap the string in `Tpl` to ask for rendering:

```python
from zrb import CmdTask, StrInput, Tpl, cli

cli.add_task(CmdTask(name="literal", cmd="echo '{not-a-template}'"))

cli.add_task(
    CmdTask(
        name="templated",
        input=StrInput(name="who", default="world"),
        cmd=Tpl("echo 'hello {ctx.input.who}'"),
    )
)
```

`Tpl` is accepted anywhere an attribute is typed `StrAttr`, `BoolAttr`, `IntAttr`
or `FloatAttr` — it renders to text, and the attribute's own type coerces the
result (`BoolAttr` through `to_boolean`, `IntAttr` through `int`).

A callable `(ctx) -> value` is the third option, and the one to reach for when the
value needs branching or a call into your own code. Prefer `Tpl` inside a loop,
though: `Tpl(f"echo {n}")` binds `n` eagerly, while `lambda ctx: f"echo {n}"`
captures the *variable* and hands every task the last value.

---

## XCom (Cross-Communication)

`XCom` is the system that allows tasks to pass state to each other. It works by creating a specialized `deque` queue for every task in the session.

### Automatic Data Flow

| Step | What Happens |
|------|--------------|
| 1. Pushing | The `return` value of a task's `action` is *automatically* pushed to XCom |
| 2. Popping | Downstream tasks access data via the upstream task's queue name |

### Example: Automatic Transfer

```python
from zrb import cli, CmdTask, Task, Tpl

# This task returns "42" to its XCom queue automatically
create_magic_number = cli.add_task(
    CmdTask(name="create-magic-number", cmd="echo 42")
)

# This task consumes the value via Zrb's own {ctx.x} rendering in the command
show_magic_number = cli.add_task(
    CmdTask(
        name="show-magic-number",
        upstream=[create_magic_number], # Dependency is required!
        cmd=Tpl("echo 'The magic number is: {ctx.xcom['create-magic-number'].pop()}'")
    )
)
```

### Manual XCom Manipulation

You can manually interact with XCom queues within a Python task:

| Method | Description |
|--------|-------------|
| `ctx.xcom['task-name'].push(val)` | Add to the queue |
| `ctx.xcom['task-name'].pop()` | Remove and return oldest item |
| `ctx.xcom['task-name'].peek()` | Look at oldest item without removing |
| `ctx.xcom['task-name'].get()` | Read latest value without removing; returns `None` if empty |

### Example: Manual Transfer

```python
@make_task(name="task1", group=cli)
def task1(ctx):
    # Manual push (bypassing the return mechanism)
    ctx.xcom["task1"].push("Manual Data")

@make_task(name="task2", upstream=[task1], group=cli)
def task2(ctx):
    # Manual pop
    data = ctx.xcom["task1"].pop()
    ctx.print(f"Received: {data}")
```

> 📖 **Deep Dive:** For advanced XCom patterns — fan-in, broadcasting, pipeline stages, and edge cases — see the [XCom Deep Dive](./xcom-deep-dive.md).

---

## Ambient Context

Inside a task action, `ctx` is passed as an argument. But some helpers — like `zrb_print()` and `get_current_ctx()` — can access the active context without you passing it explicitly. This works via Python's `contextvars.ContextVar`.

When Zrb starts executing a task, it stores the task's `ctx` in a module-level `ContextVar` called `current_ctx`. Any code that runs within that task (including helper functions and nested calls) can retrieve it:

```python
from zrb.context.any_context import get_current_ctx, zrb_print

def my_helper():
    # Works anywhere inside a running task — no need to pass ctx manually
    ctx = get_current_ctx()
    ctx.log_info("Called from a helper!")

    # Or use zrb_print(), which does the same lookup internally
    zrb_print("Hello from a helper!")
```

`get_current_ctx()` raises a `RuntimeError` if called outside of a running task. `zrb_print()` falls back to the standard `print()` in that case.

> This is useful when writing utility functions that are only ever called from inside tasks and you want to avoid threading `ctx` through every function signature.

---

## Quick Reference

| Component | How to Access |
|-----------|---------------|
| Inputs | `ctx.input.<name>` |
| Env vars | `ctx.env.<name>` |
| XCom data | `ctx.xcom['task-name'].pop()` |
| Task name | Not exposed on `ctx` — use the literal string you passed as `name=...` |
| Session name | `ctx.session.name` |

---

🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > Session & Context
