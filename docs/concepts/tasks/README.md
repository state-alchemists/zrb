🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)


# Type of Tasks

There are many task types in Zrb. Every task has its own specific use cases:


- [CmdTask](cmd-task.md): Run a CLI command
- [Task (python task)](python-task.md): Run a Python function
- [DockerComposeTask](docker-compose-task.md): Run a Docker compose Command
- [ResourceMaker](resource-maker.md): Generate artifacts/resources based on templates
- [FlowTask](flow-task.md): Put `CmdTask` and `python task` into single flow.
- [RemoteCmdTask](remote-cmd-task.md)
- [RsyncTask](rsync-task.md)
- [Checkers (HttpChecker, PortChecker, and PathChecker)](checkers.md): Check parent task's readiness.

As every task are extended from `BaseTask`, you will see that most of them share some common parameters.


```
                                           BaseTask
                                               │
                                               │
  ┌──────┬───────────┬───────────┬─────────────┼─────────────────┬─────────────┬───────────┬──────────┐
  │      │           │           │             │                 │             │           │          │
  │      │           │           │             │                 │             │           │          │
  ▼      ▼           ▼           ▼             ▼                 ▼             ▼           ▼          ▼
Task  CmdTask  ResourceMaker  FlowTask  BaseRemoteCmdTask  ReccuringTask  HttpChecker PortChecker PathChecker
         │                                     │
         │                                     │
         ▼                               ┌─────┴──────┐
   DockerComposeTask                     │            │
                                         ▼            ▼
                                   RemoteCmdTask   RsyncTask
```

Aside from the documentation, you can always dive down into [the source code](https://github.com/state-alchemists/zrb/tree/main/src/zrb/task) to see the detail implementation.

> __📝 NOTE:__ Never initiate `BaseTask` directly, use `Task` instead.

# Task Overview

Tasks are building blocks of your automation.

Let's see how you can define tasks and connect them to each others:

```python
from zrb import CmdTask, IntInput, Env, Group, runner, PortChecker

# defining two groups: arasaka, and jupyterlab
# jupyterlab is located under arasaka
arasaka = Group(name='arasaka', description='Arasaka automation')
jupyterlab = Group(name='jupyterlab', parent=arasaka, description='Jupyterlab related tasks')

# defining show banner under `arasaka` group
show_banner = CmdTask(
    name='show-banner',
    icon='🎉',
    color='yellow',
    description='Show banner',
    group=arasaka,
    envs=[
        # EMPLOYEE enviornment variable will be accessible from inside the task as USER.
        # The default value this variable will be `employee`.
        Env(name='USER', os_name='EMPLOYEE', default='employee')
    ],
    cmd=[
        'figlet Arasaka',
        'echo "Welcome $USER"'
    ]
)

# registering `show_banner` to zrb runner
runner.register(show_banner)

# defining show banner under `arasaka jupyterlab` group
start_jupyterlab = CmdTask(
    name='start',
    icon='🧪',
    color='green',
    description='Start Jupyterlab',
    group=jupyterlab,
    inputs=[
        # Port where jupyterlab should be started
        IntInput(name='jupyterlab-port', default=8080)
    ],
    # start_jupyterlab depends on show_banner
    upstreams=[show_banner],
    cmd='jupyter lab --no-browser --port={{input.jupyterlab_port}}',
    checkers=[
        PortChecker(port='{{input.jupyterlab_port}}')
    ],
    retry=2,
    retry_interval=3
)

# registering `show_banner` to zrb runner
runner.register(start_jupyterlab)
```


You can try to run `start_jupyterlab` task as follow:

```bash
export EMPLOYEE="Yorinobu Arasaka"

# The following command will
# - Show Arasaka Banner
# - Start jupyterlab on the port you choose (by default it is 8080)
zrb arasaka jupyterlab start 
```

As `start_jupyterlab` has `show_banner` as it's upstream, you can expect the `show_banner` to be executed prior to `start_jupyterlab`.

A task might also have multiple upstreams. In that case, the upstreams will be executed concurrently.

> __📝 NOTE:__ Only tasks registered to `runner` are directly accessible from the CLI.

# Task Lifecycle

Every task has it's own lifecycle.

```
Triggered         ┌─────────► Ready ◄──┐
    │             │                    │
    │             │                    │
    ▼             │                    │
 Waiting ────► Started ─────► Failed   │
    │             ▲             │      │
    │             │             │      │
    ▼             │             ▼      │
 Skipped          └────────── Retry    │
    │                                  │
    │                                  │
    └──────────────────────────────────┘
```

- `Triggered`: Task is triggered.
- `Waiting`: Task is waiting all upstreams to be ready.
- `Skipped`: Task is not executed and will enter ready state soon.
- `Started`: Task has been started.
- `Failed`: Task is failed, will enter `Retry` state if retries is less than max attempt.
- `Retry`: The task has been failed and will be re-started.
- `Ready`: The task is ready.


# Technical Documentation

<!--start-doc-->
## `AnyTask`
Task class specification.

In order to create a new Task class, you have to implements all methods.
You can do this by extending BaseTask.

Currently we don't see any advantage to break this interface into
multiple interfaces since AnyTask is considered atomic.

### `AnyTask._get_checkers`
No documentation available.

### `AnyTask._get_combined_inputs`
No documentation available.

### `AnyTask._get_env_files`
No documentation available.

### `AnyTask._get_envs`
No documentation available.

### `AnyTask._get_full_cli_name`
No documentation available.

### `AnyTask._get_inputs`
No documentation available.

### `AnyTask._get_upstreams`
No documentation available.

### `AnyTask._loop_check`
No documentation available.

### `AnyTask._print_result`
No documentation available.

### `AnyTask._run_all`
No documentation available.

### `AnyTask._set_execution_id`
Set current task execution id.

This method is meant for internal use.
### `AnyTask._set_has_cli_interface`
No documentation available.

### `AnyTask._set_keyval`
No documentation available.

### `AnyTask.add_env`
Add Env to the end of the current task's env list.
If there are two Env with the same name, the later will override the first ones.
### `AnyTask.add_env_file`
Add EnvFile to the end of current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.
### `AnyTask.add_input`
Add AnyInput to the end of the current task's input list.
If there are two input with the same name, the later will override the first ones.
### `AnyTask.add_upstream`
Add AnyTask to the end of the current task's upstream list.
### `AnyTask.check`
## Description

Define how Zrb consider current task to be ready.

You can override this method.

## Example

```python
class MyTask(Task):
async def run(self, *args: Any, **kwargs: Any) -> int:
self.print_out('Doing some calculation')
self._done = True
return 42

async def check(self) -> bool:
# When self._done is True, consider the task to be "ready"
return self._done is not None and self._done
```
### `AnyTask.copy`
## Description
Return copy of the current task.

You can change properties of the copied task using any of these methods:
- `set_name`
- `set_description`
- `set_icon`
- `set_color`
- `add_upstream`
- `insert_upstream`
- `add_input`
- `insert_input`
- `add_env`
- `insert_env`
- `add_env_file`
- `insert_env_file`
- or any other methods depending on the TaskClass you use.

## Example

```python
task = Task(name='my-task', cmd='echo hello')

copied_task = task.copy()
copied_task.set_name('new_name')
```
### `AnyTask.get_cli_name`
No documentation available.

### `AnyTask.get_color`
No documentation available.

### `AnyTask.get_description`
No documentation available.

### `AnyTask.get_env_map`
No documentation available.

### `AnyTask.get_execution_id`
No documentation available.

### `AnyTask.get_icon`
No documentation available.

### `AnyTask.get_input_map`
No documentation available.

### `AnyTask.inject_checkers`
No documentation available.

### `AnyTask.inject_env_files`
No documentation available.

### `AnyTask.inject_envs`
No documentation available.

### `AnyTask.inject_inputs`
No documentation available.

### `AnyTask.inject_upstreams`
No documentation available.

### `AnyTask.insert_env`
Insert Env to the beginning of the current task's env list.
If there are two Env with the same name, the later will override the first ones.
### `AnyTask.insert_env_file`
Insert EnvFile to the beginning of the current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.
### `AnyTask.insert_input`
Insert AnyInput to the beginning of the current task's input list.
If there are two input with the same name, the later will override the first ones.
### `AnyTask.insert_upstream`
Insert AnyTask to the beginning of the current task's upstream list.
### `AnyTask.log_critical`
No documentation available.

### `AnyTask.log_debug`
No documentation available.

### `AnyTask.log_error`
No documentation available.

### `AnyTask.log_info`
No documentation available.

### `AnyTask.log_warn`
No documentation available.

### `AnyTask.on_failed`
## Description

Define what to do when the current task status is `failed`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_failed(self, is_last_attempt: bool, exception: Exception):
if is_last_attempt:
self.print_out('The task is failed, and there will be no retry')
raise exception
self.print_out('The task is failed, going to retry')
```
### `AnyTask.on_ready`
## Description

Define what to do when the current task status is `ready`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_ready(self):
self.print_out('The task is ready')
```
### `AnyTask.on_retry`
## Description

Define what to do when the current task status is `retry`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_retry(self):
self.print_out('The task is retrying')
```
### `AnyTask.on_skipped`
## Description

Define what to do when the current task status is `skipped`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_skipped(self):
self.print_out('The task is not started')
```
### `AnyTask.on_started`
## Description

Define what to do when the current task status is `started`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_started(self):
self.print_out('The task is started')
```
### `AnyTask.on_triggered`
## Description

Define what to do when the current task status is `triggered`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_triggered(self):
self.print_out('The task has been triggered')
```
### `AnyTask.on_waiting`
## Description

Define what to do when the current task status is `waiting`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_waiting(self):
self.print_out('The task is waiting to be started')
```
### `AnyTask.print_err`
No documentation available.

### `AnyTask.print_out`
No documentation available.

### `AnyTask.print_out_dark`
No documentation available.

### `AnyTask.print_result`
Print result to stdout so that it can be processed further.
e.g.: echo $(zrb explain solid) > solid-principle.txt

You need to override this method
if you want to show the result differently.
### `AnyTask.render_any`
No documentation available.

### `AnyTask.render_bool`
No documentation available.

### `AnyTask.render_file`
No documentation available.

### `AnyTask.render_float`
No documentation available.

### `AnyTask.render_int`
No documentation available.

### `AnyTask.render_str`
No documentation available.

### `AnyTask.run`
## Description

Define what to do when current task is started.

You can override this method.

## Example

```python
class MyTask(Task):
async def run(self, *args: Any, **kwargs: Any) -> int:
self.print_out('Doing some calculation')
return 42
```
### `AnyTask.set_checking_interval`
No documentation available.

### `AnyTask.set_color`
No documentation available.

### `AnyTask.set_description`
Set current task description.
Usually used to overide copied task's description.
### `AnyTask.set_icon`
Set current task icon.
Usually used to overide copied task's icon.
### `AnyTask.set_name`
Set current task name.
Usually used to overide copied task's name.
### `AnyTask.set_retry`
No documentation available.

### `AnyTask.set_retry_interval`
No documentation available.

### `AnyTask.set_should_execute`
No documentation available.

### `AnyTask.to_function`
Turn current task into a callable.
<!--end-doc-->


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)
