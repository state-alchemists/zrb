🔖 [Home](../../../README.md) > [Documentation](../../../../README.md) > [Core Concepts](../../README.md) > [Session and Context](./README.md) > [XCom](./xcom.md)

# XCom (Cross-Communication)

`XCom` is the secret sauce for making your tasks talk to each other. It's a simple yet powerful mechanism for passing small pieces of data—like results, IDs, or status messages—from one task to another.

Think of `XCom` as a shared dictionary of message queues available during a session. Each task can have its own named queue where it can `push` data, and other tasks can `pop` data from it.

Zrb makes this even easier: by default, the return value of a task's `action` is automatically pushed to its `XCom` queue.

You can access `XCom` through the context object: `ctx.xcom`.

## A Simple Data-Passing Example

Here's a classic example: one task creates a "magic number," and a second task uses it.

```python
from zrb import cli, CmdTask

# This task's output (42) will be automatically pushed to its XCom queue
create_magic_number = CmdTask(name="create-magic-number", cmd="echo 42")

cli.add_task(
  CmdTask(
    name="show-magic-number",
    upstream=[create_magic_number],
    # Here, we pop the value from the upstream task's queue
    cmd="echo 'The magic number is: {ctx.xcom['create-magic-number'].pop()}'",
  )
)
```

When you run `zrb show-magic-number`, Zrb first runs `create-magic-number`, captures its output ("42"), and places it in the `xcom['create-magic-number']` queue. Then, `show-magic-number` runs and retrieves that value.

## How to Use XCom Manually

While Zrb automatically pushes return values, you can also push and pop data manually within your task's logic.

*   **Pushing data:** `ctx.xcom[ctx.task_name].push("some data")`
*   **Popping data:** `data = ctx.xcom['upstream_task_name'].pop()`
*   **Peeking at data:** `data = ctx.xcom['upstream_task_name'].peek()` (gets the value without removing it)

## Manual Pushing Example

Here's a more explicit example using Python tasks.

```python
from zrb import Task, cli

# Task 1: Manually pushes a message to its XCom queue
task1 = Task(
    name="task1",
    description="Pushes data to XCom",
    action=lambda ctx: ctx.xcom[ctx.task_name].push("Hello from Task 1!")
)

# Task 2: Depends on Task 1 and pulls the data
task2 = Task(
    name="task2",
    description="Pulls data from Task 1's XCom",
    upstream=[task1], # This dependency is crucial!
    action=lambda ctx: print(f"Task 2 received: {ctx.xcom['task1'].pop()}")
)

cli.add_task(task1)
cli.add_task(task2)
```

`XCom` is perfect for passing small, serializable pieces of data. For larger data or more complex communication, you might consider other methods like writing to a file.