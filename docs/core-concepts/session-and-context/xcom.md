🔖 [Home](../../../README.md) > [Documentation](../../../../README.md) > [Core Concepts](../../README.md) > [Session and Context](./README.md) > [XCom](./xcom.md)

# XCom

Use `xcom` for inter-`task` communication.

You can think of `xcom` as a dictionary of [`deque`](https://docs.python.org/3/library/collections.html#collections.deque). You can manually create a key and push a value to it or pop its value.

Zrb automatically pushes a task's return value to the `xcom`.

You can access `xcom` by using `ctx.xcom`.

```python
from zrb import cli, CmdTask

create_magic_number = CmdTask(name="create-magic-number", cmd="echo 42")
cli.add_task(
  CmdTask(
    name="show-magic-number",
    upstream=create_magic_number,
    cmd="echo {ctx.xcom['create-magic-number'].pop()}",
  )
)
```

XCom, or Cross-Communication, is a mechanism in Zrb that allows tasks to exchange small amounts of data. This is particularly useful for passing results or information between dependent tasks in a workflow.

Each task in a Zrb session has its own XCom queue, which acts like a simple message queue. Tasks can push data to their own XCom queue, and other tasks can pull data from the XCom queues of their upstream dependencies.

## How to Use XCom

You can access a task's XCom queue via the `ctx.xcom` object within a task's `action`. `ctx.xcom` is a dictionary-like object where keys are task names and values are the XCom queues (specifically, `Xcom` objects, which behave like Python `deque`s).

To push data to the current task's XCom queue:

```python
# Inside a task's action
ctx.xcom[ctx.task_name].push("some data")
```

To pull data from an upstream task's XCom queue:

```python
# Inside a task's action that depends on 'upstream_task'
data = ctx.xcom['upstream_task'].pop()
print(f"Received data from upstream: {data}")
```

You can also peek at the next item in the queue without removing it using `peek()`.

## Example

Here's a simple example demonstrating how one task can pass data to another using XCom:

```python
from zrb import Task, cli

# Task 1: Pushes data to its XCom
task1 = Task(
    name="task1",
    description="Pushes data to XCom",
    action=lambda ctx: ctx.xcom[ctx.task_name].push("Hello from Task 1!")
)

# Task 2: Depends on Task 1 and pulls data from its XCom
task2 = Task(
    name="task2",
    description="Pulls data from Task 1's XCom",
    upstream=[task1], # Define dependency
    action=lambda ctx: print(f"Task 2 received: {ctx.xcom['task1'].pop()}")
)

cli.add_task(task1)
cli.add_task(task2)

# When you run task2, task1 will execute first, push data,
# and then task2 will execute and retrieve the data.
```

XCom is designed for passing small, serializable data between tasks. For larger data or more complex inter-task communication patterns, consider alternative approaches.