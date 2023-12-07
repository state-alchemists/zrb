
🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# FlowTask

FlowTask allows you to compose several unrelated tasks/actions into a single tasks.

```python
from zrb import FlowTask, CmdTask, HttpChecker, runner
import os

CURRENT_DIR = os.dirname(__file__)

prepare_backend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(CURRENT_DIR, 'app', 'backend'),
    cmd='pip install -r requirements.txt'
)

prepare_frontend = CmdTask(
    name='prepare-backend',
    cwd=os.path.join(CURRENT_DIR, 'app', 'frontend'),
    cmd='npm install && npm run build'
)

start_app = CmdTask(
    name='start-app',
    cwd=os.path.join(CURRENT_DIR, 'app', 'backend'),
    cmd='uvicorn main:app --port 8080',
    checkers=[
        HttpChecker(port=8080)
    ]
)

prepare_and_start_app = FlowTask(
    name='prepare-and-start-app',
    steps=[
        # Prepare backend and frontend concurrently
        [
            prepare_backend,
            prepare_frontend
        ],
        # Then start app
        start_app,
        # And finally show instruction
        CmdTask(
            name='show-instruction',
            cmd='echo "App is ready, Check your browser"'
        )
    ]
)
runner.register(prepare_app)
```

# Technical Documentation

<!--start-doc-->
## `FlowTask`

Base class for all tasks.
Every task definition should be extended from this class.

### `FlowTask._BaseTaskModel__get_colored`

No documentation available.


### `FlowTask._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `FlowTask._BaseTaskModel__get_common_prefix`

No documentation available.


### `FlowTask._BaseTaskModel__get_executable_name`

No documentation available.


### `FlowTask._BaseTaskModel__get_log_prefix`

No documentation available.


### `FlowTask._BaseTaskModel__get_print_prefix`

No documentation available.


### `FlowTask._BaseTaskModel__get_rjust_full_cli_name`

No documentation available.


### `FlowTask._Renderer__ensure_cached_render_data`

No documentation available.


### `FlowTask._Renderer__get_render_data`

No documentation available.


### `FlowTask._cached_check`

No documentation available.


### `FlowTask._cached_run`

No documentation available.


### `FlowTask._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `FlowTask._check_should_execute`

No documentation available.


### `FlowTask._end_timer`

No documentation available.


### `FlowTask._get_attempt`

No documentation available.


### `FlowTask._get_checkers`

No documentation available.


### `FlowTask._get_combined_env`

No documentation available.


### `FlowTask._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `FlowTask._get_elapsed_time`

No documentation available.


### `FlowTask._get_embeded_tasks`

No documentation available.


### `FlowTask._get_env_files`

No documentation available.


### `FlowTask._get_envs`

No documentation available.


### `FlowTask._get_full_cli_name`

No documentation available.


### `FlowTask._get_inputs`

No documentation available.


### `FlowTask._get_max_attempt`

No documentation available.


### `FlowTask._get_task_pid`

No documentation available.


### `FlowTask._get_upstreams`

No documentation available.


### `FlowTask._increase_attempt`

No documentation available.


### `FlowTask._is_done`

No documentation available.


### `FlowTask._is_last_attempt`

No documentation available.


### `FlowTask._lock_upstreams`

No documentation available.


### `FlowTask._loop_check`

No documentation available.


### `FlowTask._mark_awaited`

No documentation available.


### `FlowTask._mark_done`

No documentation available.


### `FlowTask._play_bell`

No documentation available.


### `FlowTask._print_result`

No documentation available.


### `FlowTask._propagate_execution_id`

No documentation available.


### `FlowTask._run_all`

No documentation available.


### `FlowTask._run_and_check_all`

No documentation available.


### `FlowTask._set_args`

No documentation available.


### `FlowTask._set_env_map`

No documentation available.


### `FlowTask._set_execution_id`

Set current task execution id.

This method is meant for internal use.

### `FlowTask._set_has_cli_interface`

No documentation available.


### `FlowTask._set_input_map`

No documentation available.


### `FlowTask._set_keyval`

No documentation available.


### `FlowTask._set_kwargs`

No documentation available.


### `FlowTask._set_local_keyval`

No documentation available.


### `FlowTask._set_task_pid`

No documentation available.


### `FlowTask._should_attempt`

No documentation available.


### `FlowTask._show_done_info`

No documentation available.


### `FlowTask._show_env_prefix`

No documentation available.


### `FlowTask._show_run_command`

No documentation available.


### `FlowTask._start_timer`

No documentation available.


### `FlowTask._step_to_tasks`

No documentation available.


### `FlowTask.add_env`

Add Env to the end of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `FlowTask.add_env_file`

Add EnvFile to the end of current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `FlowTask.add_input`

Add AnyInput to the end of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `FlowTask.add_upstream`

Add AnyTask to the end of the current task's upstream list.

### `FlowTask.check`

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

### `FlowTask.copy`

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

### `FlowTask.get_cli_name`

No documentation available.


### `FlowTask.get_color`

No documentation available.


### `FlowTask.get_description`

No documentation available.


### `FlowTask.get_env_map`

No documentation available.


### `FlowTask.get_execution_id`

No documentation available.


### `FlowTask.get_icon`

No documentation available.


### `FlowTask.get_input_map`

No documentation available.


### `FlowTask.inject_checkers`

No documentation available.


### `FlowTask.inject_env_files`

No documentation available.


### `FlowTask.inject_envs`

No documentation available.


### `FlowTask.inject_inputs`

No documentation available.


### `FlowTask.inject_upstreams`

No documentation available.


### `FlowTask.insert_env`

Insert Env to the beginning of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `FlowTask.insert_env_file`

Insert EnvFile to the beginning of the current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `FlowTask.insert_input`

Insert AnyInput to the beginning of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `FlowTask.insert_upstream`

Insert AnyTask to the beginning of the current task's upstream list.

### `FlowTask.log_critical`

No documentation available.


### `FlowTask.log_debug`

No documentation available.


### `FlowTask.log_error`

No documentation available.


### `FlowTask.log_info`

No documentation available.


### `FlowTask.log_warn`

No documentation available.


### `FlowTask.on_failed`

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

### `FlowTask.on_ready`

## Description

Define what to do when the current task status is `ready`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_ready(self):
self.print_out('The task is ready')
```

### `FlowTask.on_retry`

## Description

Define what to do when the current task status is `retry`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_retry(self):
self.print_out('The task is retrying')
```

### `FlowTask.on_skipped`

## Description

Define what to do when the current task status is `skipped`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_skipped(self):
self.print_out('The task is not started')
```

### `FlowTask.on_started`

## Description

Define what to do when the current task status is `started`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_started(self):
self.print_out('The task is started')
```

### `FlowTask.on_triggered`

## Description

Define what to do when the current task status is `triggered`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_triggered(self):
self.print_out('The task has been triggered')
```

### `FlowTask.on_waiting`

## Description

Define what to do when the current task status is `waiting`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_waiting(self):
self.print_out('The task is waiting to be started')
```

### `FlowTask.print_err`

No documentation available.


### `FlowTask.print_out`

No documentation available.


### `FlowTask.print_out_dark`

No documentation available.


### `FlowTask.print_result`

Print result to stdout so that it can be processed further.
e.g.: echo $(zrb explain solid) > solid-principle.txt

You need to override this method
if you want to show the result differently.

### `FlowTask.render_any`

No documentation available.


### `FlowTask.render_bool`

No documentation available.


### `FlowTask.render_file`

No documentation available.


### `FlowTask.render_float`

No documentation available.


### `FlowTask.render_int`

No documentation available.


### `FlowTask.render_str`

No documentation available.


### `FlowTask.run`

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

### `FlowTask.set_checking_interval`

No documentation available.


### `FlowTask.set_color`

No documentation available.


### `FlowTask.set_description`

Set current task description.
Usually used to overide copied task's description.

### `FlowTask.set_icon`

Set current task icon.
Usually used to overide copied task's icon.

### `FlowTask.set_name`

Set current task name.
Usually used to overide copied task's name.

### `FlowTask.set_retry`

No documentation available.


### `FlowTask.set_retry_interval`

No documentation available.


### `FlowTask.set_should_execute`

No documentation available.


### `FlowTask.to_function`

Turn current task into a callable.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)