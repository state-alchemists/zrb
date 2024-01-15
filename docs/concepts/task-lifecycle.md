🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Task Lifecycle

<div align="center">
  <img height="60em" src="../_images/emoji/poultry_leg.png"/>
  <img height="100em" src="../_images/emoji/chicken.png"/>
  <img height="80em" src="../_images/emoji/baby_chick.png">
  <img height="60em" src="../_images/emoji/hatching_chick.png">
  <img height="50em" src="../_images/emoji/egg.png">
  <p>
    <sub>
      All that grows must also wither and die, then nourish the living.
    </sub>
  </p>
</div>



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
- `Skipped`: The Task is not executed and will immediately enter the `Ready` state.
- `Started`: The Task execution is started.
- `Failed`: The Task execution is failed. It will enter the `Retry` state if the current attempt is less than the maximum attempt.
- `Retry`: The task will be restarted.
- `Ready`: The task is ready.

# Set Maximum Retry

Most Zrb Tasks have a retry mechanism. For `Task` and `CmdTask`, the default retry is two.

To override the maximum retries, you can use the `retry` attribute.

```python
from zrb import runner, CmdTask

update_ubuntu = CmdTask(
    name='update-ubuntu',
    cmd='sudo apt update && sudo apt upgrade -y',
    preexec_fn=None, # Let the user interact with the command
    retry=3 # Will retry three times more if failed.
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

Now, whenever you run `zrb update-ubuntu` on a non-Linux machine, the Task will enter `Ready` state without actually doing the execution.

# Long Running Task

We often need to set Zrb Task as `Ready` even though the process is still running. For example, when we run a web server. We can say a web server is `Ready` when it serves HTTP requests correctly. 

Zrb Tasks has `checkers` attributes. This attribute helps you to define the current Task's readiness.

Let's see the following example.

```python
from zrb import runner, CmdTask, HTTPChecker

start_server = CmdTask(
    name='start-server',
    cmd='python -m http.server 8080',
    checkers=[
        HTTPChecker(port=8080)
    ]
)
runner.register(start_server)
```

In the example, `start-server` is `ready` once a request to `http://localhost:8080` returns `HTTP response 200`.

Zrb provides some built-in [checkers](specialized-tasks/checker.md) you can use.


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
