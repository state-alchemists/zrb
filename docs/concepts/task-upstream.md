🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Task Upstream

In Zrb, you can define task upstreams (dependencies).

A Task will only be `started` or `skipped` if all its upstreams are `ready`.

Furthermore, the upstreams might run in parallel/concurrently.

To define Task Upstreams, you can use `upstreams` attribute like the following.

Let's see the following example.

```python
from zrb import runner, python_task, CmdTask
import asyncio

@python_task(
    name='upstream-1'
)
async def upstream_1(*args, **kwargs):
    task = kwargs.get('_task')
    for i in range(5):
        await asyncio.sleep(1)
        task.print_out(f'upstream-1 {i}') 
    return 'ok'

@python_task(
    name='upstream-2'
)
async def upstream_2(*args, **kwargs):
    task = kwargs.get('_task')
    for i in range(5):
        await asyncio.sleep(1)
        task.print_out(f'upstream-2 {i}') 
    return 'ok'

task = CmdTask(
    name='task',
    upstreams=[upstream_1, upstream_2],
    cmd='echo OK'
)
runner.register(task)
```

Alternatively, you can also use shift-right operator (i.e., `>>`):

```python
from zrb import runner, Parallel, python_task, CmdTask
import asyncio

@python_task(
    name='upstream-1'
)
async def upstream_1(*args, **kwargs):
    task = kwargs.get('_task')
    for i in range(5):
        await asyncio.sleep(1)
        task.print_out(f'upstream-1 {i}') 
    return 'ok'

@python_task(
    name='upstream-2'
)
async def upstream_2(*args, **kwargs):
    task = kwargs.get('_task')
    for i in range(5):
        await asyncio.sleep(1)
        task.print_out(f'upstream-2 {i}') 
    return 'ok'

task = CmdTask(
    name='task',
    cmd='echo OK'
)


# Define dependencies
Parallel(upstream_1, upstream_2) >> task

# Register task
runner.register(task)
```


When you run the task (i.e., by executing `zrb task`), you can see that `task` will never be started unless `upstream-1` and `upstream-2` are ready.

```
upstream-1    Triggered──► Waiting──► Started──► Ready───┐
                                                         ├───┐
upstream-2    Triggered──► Waiting──► Started──► Ready───┘   │
                                                             ▼
task          Triggered──► Waiting──────────────────────► Started──► Ready
```

# Upstream and Retry

Zrb Tasks has a default retry mechanism. For example, default retry attempts for `CmdTask` and `Task` are two.

Using upstreams, you can ensure that Zrb will only retry a small subset of your workflow in case of failure.

Let's see the following example:

```python
from zrb import runner, CmdTask

update = CmdTask(
    name='update',
    cmd='sudo apt update',
    preexec_fn=None
)

upgrade = CmdTask(
    name='upgrade',
    cmd='sudo apt upgrade -y',
    preexec_fn=None
)

install_cowsay = CmdTask(
    name='install-cowsay',
    cmd='sudo apt install cowsay',
    preexec_fn=None
)

update >> upgrade >> install_cowsay
runner.register(install_cowsay)
```

In the example, we split our workflow into three tasks that depend on each other.

Let's say you have a connection glitch while doing `upgrade`. Zrb will only retry the `upgrade` task instead of the whole workflow. This mechanism will save your computing resources. 

# Next

Next, you can learn about [environments](environments.md) and [inputs](inputs.md).

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
