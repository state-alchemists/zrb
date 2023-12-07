🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# RsyncTask

```python
from zrb import (
    runner, CmdTask, RsyncTask, RemoteConfig, PasswordInput, StrInput
)

upload = RsyncTask(
    name='upload',
    inputs=[
        PasswordInput(name='passsword'),
        StrInput(name='src'),
        StrInput(name='dst'),
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}',
            config_map={
                'dir': '192-168-1-10'
            }
        )
    ],
    is_remote_src=False,
    src='$_CONFIG_MAP_DIR/{{input.src}}',
    is_remote_dst=True,
    dst='{{input.dst}}',
)
runner.register(upload)

download = RsyncTask(
    name='download',
    inputs=[
        PasswordInput(name='passsword'),
        StrInput(name='src'),
        StrInput(name='dst'),
    ],
    remote_configs=[
        RemoteConfig(
            host='192.168.1.10,
            user='ubuntu,
            password='{{input.password}}'
        )
    ],
    is_remote_src=True,
    src='{{input.src}}',
    is_remote_dst=False,
    dst='$_CONFIG_MAP_DIR/{{input.dst}}',
)
runner.register(download)
```

RsyncTask exposes several environments that you can use on your `src` and `dst`

- `_CONFIG_HOST`
- `_CONFIG_PORT`
- `_CONFIG_SSH_KEY`
- `_CONFIG_USER`
- `_CONFIG_PASSWORD`
- `_CONFIG_MAP_<UPPER_SNAKE_CASE_NAME>`


# Technical Documentation

<!--start-doc-->
## `RsyncTask`

Base class for all tasks.
Every task definition should be extended from this class.

### `RsyncTask._BaseTaskModel__get_colored`

No documentation available.


### `RsyncTask._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `RsyncTask._BaseTaskModel__get_common_prefix`

No documentation available.


### `RsyncTask._BaseTaskModel__get_executable_name`

No documentation available.


### `RsyncTask._BaseTaskModel__get_log_prefix`

No documentation available.


### `RsyncTask._BaseTaskModel__get_print_prefix`

No documentation available.


### `RsyncTask._BaseTaskModel__get_rjust_full_cli_name`

No documentation available.


### `RsyncTask._Renderer__ensure_cached_render_data`

No documentation available.


### `RsyncTask._Renderer__get_render_data`

No documentation available.


### `RsyncTask._cached_check`

No documentation available.


### `RsyncTask._cached_run`

No documentation available.


### `RsyncTask._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `RsyncTask._check_should_execute`

No documentation available.


### `RsyncTask._end_timer`

No documentation available.


### `RsyncTask._get_attempt`

No documentation available.


### `RsyncTask._get_checkers`

No documentation available.


### `RsyncTask._get_combined_env`

No documentation available.


### `RsyncTask._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `RsyncTask._get_elapsed_time`

No documentation available.


### `RsyncTask._get_env_files`

No documentation available.


### `RsyncTask._get_envs`

No documentation available.


### `RsyncTask._get_full_cli_name`

No documentation available.


### `RsyncTask._get_inputs`

No documentation available.


### `RsyncTask._get_max_attempt`

No documentation available.


### `RsyncTask._get_parsed_path`

No documentation available.


### `RsyncTask._get_task_pid`

No documentation available.


### `RsyncTask._get_upstreams`

No documentation available.


### `RsyncTask._increase_attempt`

No documentation available.


### `RsyncTask._is_done`

No documentation available.


### `RsyncTask._is_last_attempt`

No documentation available.


### `RsyncTask._lock_upstreams`

No documentation available.


### `RsyncTask._loop_check`

No documentation available.


### `RsyncTask._mark_awaited`

No documentation available.


### `RsyncTask._mark_done`

No documentation available.


### `RsyncTask._play_bell`

No documentation available.


### `RsyncTask._print_result`

No documentation available.


### `RsyncTask._propagate_execution_id`

No documentation available.


### `RsyncTask._run_all`

No documentation available.


### `RsyncTask._run_and_check_all`

No documentation available.


### `RsyncTask._set_args`

No documentation available.


### `RsyncTask._set_env_map`

No documentation available.


### `RsyncTask._set_execution_id`

Set current task execution id.

This method is meant for internal use.

### `RsyncTask._set_has_cli_interface`

No documentation available.


### `RsyncTask._set_input_map`

No documentation available.


### `RsyncTask._set_keyval`

No documentation available.


### `RsyncTask._set_kwargs`

No documentation available.


### `RsyncTask._set_local_keyval`

No documentation available.


### `RsyncTask._set_task_pid`

No documentation available.


### `RsyncTask._should_attempt`

No documentation available.


### `RsyncTask._show_done_info`

No documentation available.


### `RsyncTask._show_env_prefix`

No documentation available.


### `RsyncTask._show_run_command`

No documentation available.


### `RsyncTask._start_timer`

No documentation available.


### `RsyncTask.add_env`

Add Env to the end of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `RsyncTask.add_env_file`

Add EnvFile to the end of current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `RsyncTask.add_input`

Add AnyInput to the end of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `RsyncTask.add_upstream`

Add AnyTask to the end of the current task's upstream list.

### `RsyncTask.check`

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

### `RsyncTask.copy`

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

### `RsyncTask.get_cli_name`

No documentation available.


### `RsyncTask.get_color`

No documentation available.


### `RsyncTask.get_description`

No documentation available.


### `RsyncTask.get_env_map`

No documentation available.


### `RsyncTask.get_execution_id`

No documentation available.


### `RsyncTask.get_icon`

No documentation available.


### `RsyncTask.get_input_map`

No documentation available.


### `RsyncTask.inject_checkers`

No documentation available.


### `RsyncTask.inject_env_files`

No documentation available.


### `RsyncTask.inject_envs`

No documentation available.


### `RsyncTask.inject_inputs`

No documentation available.


### `RsyncTask.inject_upstreams`

No documentation available.


### `RsyncTask.insert_env`

Insert Env to the beginning of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `RsyncTask.insert_env_file`

Insert EnvFile to the beginning of the current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `RsyncTask.insert_input`

Insert AnyInput to the beginning of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `RsyncTask.insert_upstream`

Insert AnyTask to the beginning of the current task's upstream list.

### `RsyncTask.log_critical`

No documentation available.


### `RsyncTask.log_debug`

No documentation available.


### `RsyncTask.log_error`

No documentation available.


### `RsyncTask.log_info`

No documentation available.


### `RsyncTask.log_warn`

No documentation available.


### `RsyncTask.on_failed`

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

### `RsyncTask.on_ready`

## Description

Define what to do when the current task status is `ready`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_ready(self):
self.print_out('The task is ready')
```

### `RsyncTask.on_retry`

## Description

Define what to do when the current task status is `retry`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_retry(self):
self.print_out('The task is retrying')
```

### `RsyncTask.on_skipped`

## Description

Define what to do when the current task status is `skipped`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_skipped(self):
self.print_out('The task is not started')
```

### `RsyncTask.on_started`

## Description

Define what to do when the current task status is `started`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_started(self):
self.print_out('The task is started')
```

### `RsyncTask.on_triggered`

## Description

Define what to do when the current task status is `triggered`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_triggered(self):
self.print_out('The task has been triggered')
```

### `RsyncTask.on_waiting`

## Description

Define what to do when the current task status is `waiting`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_waiting(self):
self.print_out('The task is waiting to be started')
```

### `RsyncTask.print_err`

No documentation available.


### `RsyncTask.print_out`

No documentation available.


### `RsyncTask.print_out_dark`

No documentation available.


### `RsyncTask.print_result`

Print result to stdout so that it can be processed further.
e.g.: echo $(zrb explain solid) > solid-principle.txt

You need to override this method
if you want to show the result differently.

### `RsyncTask.render_any`

No documentation available.


### `RsyncTask.render_bool`

No documentation available.


### `RsyncTask.render_file`

No documentation available.


### `RsyncTask.render_float`

No documentation available.


### `RsyncTask.render_int`

No documentation available.


### `RsyncTask.render_str`

No documentation available.


### `RsyncTask.run`

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

### `RsyncTask.set_checking_interval`

No documentation available.


### `RsyncTask.set_color`

No documentation available.


### `RsyncTask.set_description`

Set current task description.
Usually used to overide copied task's description.

### `RsyncTask.set_icon`

Set current task icon.
Usually used to overide copied task's icon.

### `RsyncTask.set_name`

Set current task name.
Usually used to overide copied task's name.

### `RsyncTask.set_retry`

No documentation available.


### `RsyncTask.set_retry_interval`

No documentation available.


### `RsyncTask.set_should_execute`

No documentation available.


### `RsyncTask.to_function`

Turn current task into a callable.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
