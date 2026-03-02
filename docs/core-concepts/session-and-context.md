🔖 [Documentation Home](../../README.md) > [Core Concepts](./) > Session & Context

# Session, Context, and XCom

To understand how data flows through a Zrb pipeline, you must understand the relationship between a `Session`, a `Context`, and `XCom`.

## What's the Difference?

- **`Session`**: The entire factory floor. It manages a single run of a workflow from start to finish, resolving dependencies and tracking task states (pending, running, completed, failed).
- **`Context` (`ctx`)**: The specific workbench for a single task. It contains only what the current task needs to do its job: inputs, environments, logging utilities, and the XCom mailbox.
- **`XCom`**: The conveyor belt between workbenches. It allows Task A to send a piece of data to Task B.

---

## The Context (`ctx`)

When a task executes its `action`, Zrb passes it a `Context` object, universally referred to as `ctx`.

### Shared Data Plane
The context holds information that is aggregated from the task and all its upstreams:
- `ctx.input`: Access parsed user inputs.
- `ctx.env`: Access resolved environment variables.
- `ctx.xcom`: Access the data-sharing queues.

### Task-Specific Utilities
The context provides methods specific to the currently executing task:
- `ctx.print(*values)`: Formatted printing (includes the task's color and name).
- `ctx.log_info(msg)`, `ctx.log_error(msg)`: Logs messages to the shared session log.
- `ctx.render(template_string)`: Renders a Jinja2 f-string against the context variables.

```python
from zrb import Task, cli, StrInput

@make_task(name="context-demo", group=cli, input=StrInput(name="user", default="Zrb"))
def demo(ctx):
    # Logging
    ctx.log_info("Task started")
    
    # Rendering
    rendered = ctx.render("Hello {{ctx.input.user}}!")
    
    # Printing
    ctx.print(rendered)
```

---

## XCom (Cross-Communication)

`XCom` is the system that allows tasks to pass state to each other. It works by creating a specialized `deque` queue for every task in the session.

### Automatic Data Flow

1. **Pushing**: The `return` value of a task's `action` is *automatically* pushed into that task's XCom queue.
2. **Popping**: Downstream tasks can access this data by requesting it from the upstream task's queue name.

```python
from zrb import cli, CmdTask, Task

# This task returns "42" to its XCom queue automatically
create_magic_number = cli.add_task(
    CmdTask(name="create-magic-number", cmd="echo 42")
)

# This task consumes the value via Jinja templating in the command
show_magic_number = cli.add_task(
    CmdTask(
        name="show-magic-number",
        upstream=[create_magic_number], # Dependency is required!
        cmd="echo 'The magic number is: {ctx.xcom['create-magic-number'].pop()}'"
    )
)
```

### Manual XCom Manipulation

You can manually interact with XCom queues within a Python task.
- `ctx.xcom['task-name'].push(val)`: Add to the queue.
- `ctx.xcom['task-name'].pop()`: Remove and return the oldest item.
- `ctx.xcom['task-name'].peek()`: Look at the oldest item without removing it.
- `ctx.xcom['task-name'].get()`: Safe retrieval; returns `None` if the queue is empty.

```python
@make_task(name="task1", group=cli)
def task1(ctx):
    # Manual push (bypassing the return mechanism)
    ctx.xcom[ctx.task_name].push("Manual Data")

@make_task(name="task2", upstream=[task1], group=cli)
def task2(ctx):
    # Manual pop
    data = ctx.xcom["task1"].pop()
    ctx.print(f"Received: {data}")
```
