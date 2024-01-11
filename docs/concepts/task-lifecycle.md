🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Task Lifecycle

All Zrb Task has the following lifecycle.

```
                                  ┌─────────────────────────────┐
                                  │                             │
                                  │                             ▼
Triggered ─────► Waiting ────► Started ─────► Failed   ┌────► Ready
                    │             ▲             │      │
                    │             │             │      │
                    ▼             │             ▼      │
                 Skipped          └────────── Retry    │
                    │                                  │
                    │                                  │
                    └──────────────────────────────────┘
```

- `Triggered`: The Task is triggered.
- `Waiting`: The Task is waiting for all upstreams to be ready.
- `Skipped`: The Task is not executed and will immediately enter ready state.
- `Started`: The Task execution is started.
- `Failed`: The Task execution is failed. It will enter `Retry` state if the current attempt is less than the maximum attempt.
- `Retry`: The task will be restarted.
- `Ready`: The task is ready.

# Set Maximum Retry

To set the maximum retries, you can use `retry` attribute.

```python
from zrb import runner, CmdTask

update_ubuntu = CmdTask(
    name='update-ubuntu',
    cmd='sudo apt update && sudo apt upgrade -y',
    preexec_fn=None, # Let the user interact with the command
    retry=2 # Will retry two times more if failed.
)
runner.register(update_ubuntu)
```

# Skip Execution

You can skip task execution by setting `should_execute` attribute to `False`.

For example, it is impossible to run `sudo apt update` if your OS is not `Linux`. Thus, you should only execute the Task if `sys.platform == 'Linux'`

```python
from zrb import runner, CmdTask
import sys

update_ubuntu = CmdTask(
    name='update-ubuntu',
    cmd='sudo apt update && sudo apt upgrade -y',
    preexec_fn=None, # Let the user interact with the command
    retry=2, # Will retry two times more if failed.
    should_execute=sys.platform == 'Linux'
)
runner.register(update_ubuntu)
```

Now, whenever you run `zrb update-ubuntu` on a non-Linux machine, the Task will enter `ready` state without actually do the execution.

# Handling Task Lifecycle

You can make your Task do something when it enters a particular state. To do this, you can define the following properties:

- `on_triggered`
- `on_waiting`
- `on_skipped`
- `on_started`
- `on_ready`
- `on_retry`
- `on_failed`

Let's see an example:

```python
from zrb import runner, CmdTask

def on_triggered(task: Task):
    task.print_out('Triggered')

def on_waiting(task: Task):
    task.print_out('Waiting')

def on_skipped(task: Task):
    task.print_out('Skipped')

def on_started(task: Task):
    task.print_out('Started')

def on_ready(task: Task):
    task.print_out('Ready')

def on_retry(task: Task):
    task.print_out('Retry')

def on_failed(task: Task, is_last_attempt: bool, exception: Exception):
    if is_last_attempt:
        task.print_out('Critically Failed')
        task.print_err(exception)
    task.print_out('Failed')

update_ubuntu = CmdTask(
    name='update-ubuntu',
    cmd='sudo apt update && sudo apt upgrade -y',
    preexec_fn=None, # Let the user interact with the command
    retry=2, # Will retry two times more if failed.
    on_triggered=on_triggered,
    on_waiting=on_waiting,
    on_skipped=on_skipped,
    on_started=on_started,
    on_ready=on_ready,
    on_retry=on_retry,
)
runner.register(update_ubuntu)
```

# Next

You have seen how to handle Task Lifecycle in Zrb. Next, you can learn about [Task Upstream](task-upstream.md).

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
