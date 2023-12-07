🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# RemoteCmdTask

```python
from zrb import (
    runner, CmdTask, RemoteCmdTask, RemoteConfig, PasswordInput
)

install_curl = RemoteCmdTask(
    name='install-curl',
    inputs=[
        PasswordInput(name='passsword')
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}'
        )
    ],
    cmd=[
        'sudo apt update',
        'sudo apt install curl --y'
    ]
)
runner.register(install_curl)
```

RemoteCmdTask exposes several environments that you can use on your `cmd` and `cmd_path`

- `_CONFIG_HOST`
- `_CONFIG_PORT`
- `_CONFIG_SSH_KEY`
- `_CONFIG_USER`
- `_CONFIG_PASSWORD`
- `_CONFIG_MAP_<UPPER_SNAKE_CASE_NAME>`


# Technical Documentation

<!--start-doc-->
## `RemoteCmdTask`

Base class for all tasks.
Every task definition should be extended from this class.

### `RemoteCmdTask._BaseTaskModel__get_colored`

No documentation available.


### `RemoteCmdTask._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `RemoteCmdTask._BaseTaskModel__get_common_prefix`

No documentation available.


### `RemoteCmdTask._BaseTaskModel__get_executable_name`

No documentation available.


### `RemoteCmdTask._BaseTaskModel__get_log_prefix`

No documentation available.


### `RemoteCmdTask._BaseTaskModel__get_print_prefix`

No documentation available.


### `RemoteCmdTask._BaseTaskModel__get_rjust_full_cli_name`

No documentation available.


### `RemoteCmdTask._Renderer__ensure_cached_render_data`

No documentation available.


### `RemoteCmdTask._Renderer__get_render_data`

No documentation available.


### `RemoteCmdTask._cached_check`

No documentation available.


### `RemoteCmdTask._cached_run`

No documentation available.


### `RemoteCmdTask._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `RemoteCmdTask._check_should_execute`

No documentation available.


### `RemoteCmdTask._end_timer`

No documentation available.


### `RemoteCmdTask._get_attempt`

No documentation available.


### `RemoteCmdTask._get_checkers`

No documentation available.


### `RemoteCmdTask._get_combined_env`

No documentation available.


### `RemoteCmdTask._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `RemoteCmdTask._get_elapsed_time`

No documentation available.


### `RemoteCmdTask._get_env_files`

No documentation available.


### `RemoteCmdTask._get_envs`

No documentation available.


### `RemoteCmdTask._get_full_cli_name`

No documentation available.


### `RemoteCmdTask._get_inputs`

No documentation available.


### `RemoteCmdTask._get_max_attempt`

No documentation available.


### `RemoteCmdTask._get_task_pid`

No documentation available.


### `RemoteCmdTask._get_upstreams`

No documentation available.


### `RemoteCmdTask._increase_attempt`

No documentation available.


### `RemoteCmdTask._is_done`

No documentation available.


### `RemoteCmdTask._is_last_attempt`

No documentation available.


### `RemoteCmdTask._lock_upstreams`

No documentation available.


### `RemoteCmdTask._loop_check`

No documentation available.


### `RemoteCmdTask._mark_awaited`

No documentation available.


### `RemoteCmdTask._mark_done`

No documentation available.


### `RemoteCmdTask._play_bell`

No documentation available.


### `RemoteCmdTask._print_result`

No documentation available.


### `RemoteCmdTask._propagate_execution_id`

No documentation available.


### `RemoteCmdTask._run_all`

No documentation available.


### `RemoteCmdTask._run_and_check_all`

No documentation available.


### `RemoteCmdTask._set_args`

No documentation available.


### `RemoteCmdTask._set_env_map`

No documentation available.


### `RemoteCmdTask._set_execution_id`

Set current task execution id.

This method is meant for internal use.

### `RemoteCmdTask._set_has_cli_interface`

No documentation available.


### `RemoteCmdTask._set_input_map`

No documentation available.


### `RemoteCmdTask._set_keyval`

No documentation available.


### `RemoteCmdTask._set_kwargs`

No documentation available.


### `RemoteCmdTask._set_local_keyval`

No documentation available.


### `RemoteCmdTask._set_task_pid`

No documentation available.


### `RemoteCmdTask._should_attempt`

No documentation available.


### `RemoteCmdTask._show_done_info`

No documentation available.


### `RemoteCmdTask._show_env_prefix`

No documentation available.


### `RemoteCmdTask._show_run_command`

No documentation available.


### `RemoteCmdTask._start_timer`

No documentation available.


### `RemoteCmdTask.add_env`

Add Env to the end of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `RemoteCmdTask.add_env_file`

Add EnvFile to the end of current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `RemoteCmdTask.add_input`

Add AnyInput to the end of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `RemoteCmdTask.add_upstream`

Add AnyTask to the end of the current task's upstream list.

### `RemoteCmdTask.check`

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

### `RemoteCmdTask.copy`

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

### `RemoteCmdTask.get_cli_name`

No documentation available.


### `RemoteCmdTask.get_color`

No documentation available.


### `RemoteCmdTask.get_description`

No documentation available.


### `RemoteCmdTask.get_env_map`

No documentation available.


### `RemoteCmdTask.get_execution_id`

No documentation available.


### `RemoteCmdTask.get_icon`

No documentation available.


### `RemoteCmdTask.get_input_map`

No documentation available.


### `RemoteCmdTask.inject_checkers`

No documentation available.


### `RemoteCmdTask.inject_env_files`

No documentation available.


### `RemoteCmdTask.inject_envs`

No documentation available.


### `RemoteCmdTask.inject_inputs`

No documentation available.


### `RemoteCmdTask.inject_upstreams`

No documentation available.


### `RemoteCmdTask.insert_env`

Insert Env to the beginning of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `RemoteCmdTask.insert_env_file`

Insert EnvFile to the beginning of the current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `RemoteCmdTask.insert_input`

Insert AnyInput to the beginning of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `RemoteCmdTask.insert_upstream`

Insert AnyTask to the beginning of the current task's upstream list.

### `RemoteCmdTask.log_critical`

No documentation available.


### `RemoteCmdTask.log_debug`

No documentation available.


### `RemoteCmdTask.log_error`

No documentation available.


### `RemoteCmdTask.log_info`

No documentation available.


### `RemoteCmdTask.log_warn`

No documentation available.


### `RemoteCmdTask.on_failed`

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

### `RemoteCmdTask.on_ready`

## Description

Define what to do when the current task status is `ready`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_ready(self):
self.print_out('The task is ready')
```

### `RemoteCmdTask.on_retry`

## Description

Define what to do when the current task status is `retry`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_retry(self):
self.print_out('The task is retrying')
```

### `RemoteCmdTask.on_skipped`

## Description

Define what to do when the current task status is `skipped`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_skipped(self):
self.print_out('The task is not started')
```

### `RemoteCmdTask.on_started`

## Description

Define what to do when the current task status is `started`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_started(self):
self.print_out('The task is started')
```

### `RemoteCmdTask.on_triggered`

## Description

Define what to do when the current task status is `triggered`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_triggered(self):
self.print_out('The task has been triggered')
```

### `RemoteCmdTask.on_waiting`

## Description

Define what to do when the current task status is `waiting`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_waiting(self):
self.print_out('The task is waiting to be started')
```

### `RemoteCmdTask.print_err`

No documentation available.


### `RemoteCmdTask.print_out`

No documentation available.


### `RemoteCmdTask.print_out_dark`

No documentation available.


### `RemoteCmdTask.print_result`

Print result to stdout so that it can be processed further.
e.g.: echo $(zrb explain solid) > solid-principle.txt

You need to override this method
if you want to show the result differently.

### `RemoteCmdTask.render_any`

No documentation available.


### `RemoteCmdTask.render_bool`

No documentation available.


### `RemoteCmdTask.render_file`

No documentation available.


### `RemoteCmdTask.render_float`

No documentation available.


### `RemoteCmdTask.render_int`

No documentation available.


### `RemoteCmdTask.render_str`

No documentation available.


### `RemoteCmdTask.run`

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

### `RemoteCmdTask.set_checking_interval`

No documentation available.


### `RemoteCmdTask.set_color`

No documentation available.


### `RemoteCmdTask.set_description`

Set current task description.
Usually used to overide copied task's description.

### `RemoteCmdTask.set_icon`

Set current task icon.
Usually used to overide copied task's icon.

### `RemoteCmdTask.set_name`

Set current task name.
Usually used to overide copied task's name.

### `RemoteCmdTask.set_retry`

No documentation available.


### `RemoteCmdTask.set_retry_interval`

No documentation available.


### `RemoteCmdTask.set_should_execute`

No documentation available.


### `RemoteCmdTask.to_function`

Turn current task into a callable.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
