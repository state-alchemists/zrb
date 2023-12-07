🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# Checkers

Checkers are special type of tasks. You can use checkers to check for other task's readiness.

Currently there are three types of checkers:
- PathChecker
- PortChecker
- HttpChecker


Let's say you invoke `npm run build:watch`. This command will build your Node.js App into `dist` directory, as well as watch the changes and rebuild your app as soon as there are some changes.

- A web server is considered ready if it's HTTP Port is accessible. You can use `HTTPChecker` to check for web server readiness.
- But, before running the web server to start, you need to build the frontend and make sure that the `src/frontend/dist` has been created. You can use `PathChecker` to check for frontend readiness.

Let's see how we can do this:

```python
from zrb import CmdTask, PathChecker, Env, EnvFile, runner

build_frontend = CmdTask(
    name='build-frontend',
    cmd='npm run build',
    cwd='src/frontend',
    checkers=[
        PathChecker(path='src/frontend/dist')
    ]
)

run_server = CmdTask(
    name='run-server',
    envs=[
        Env(name='PORT', os_name='WEB_PORT', default='3000')
    ],
    env_files=[
        EnvFile(env_file='src/template.env', prefix='WEB')
    ]
    cmd='python main.py',
    cwd='src',
    upstreams=[
        build_frontend
    ],
    checkers=[HTTPChecker(port='{{env.PORT}}')],
)
runner.register(run_server)
```

> Aside from `PathChecker` and `HTTPChecker`, you can also use `PortChecker` to check for TCP port readiness.

You can then run the server by invoking:

```bash
zrb run-server
```

# Technical Documentation

<!--start-doc-->
## `Checker`

Base class for all tasks.
Every task definition should be extended from this class.

### `Checker._BaseTaskModel__get_colored`

No documentation available.


### `Checker._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `Checker._BaseTaskModel__get_common_prefix`

No documentation available.


### `Checker._BaseTaskModel__get_executable_name`

No documentation available.


### `Checker._BaseTaskModel__get_log_prefix`

No documentation available.


### `Checker._BaseTaskModel__get_print_prefix`

No documentation available.


### `Checker._BaseTaskModel__get_rjust_full_cli_name`

No documentation available.


### `Checker._Renderer__ensure_cached_render_data`

No documentation available.


### `Checker._Renderer__get_render_data`

No documentation available.


### `Checker._cached_check`

No documentation available.


### `Checker._cached_run`

No documentation available.


### `Checker._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `Checker._check_should_execute`

No documentation available.


### `Checker._end_timer`

No documentation available.


### `Checker._get_attempt`

No documentation available.


### `Checker._get_checkers`

No documentation available.


### `Checker._get_combined_env`

No documentation available.


### `Checker._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `Checker._get_elapsed_time`

No documentation available.


### `Checker._get_env_files`

No documentation available.


### `Checker._get_envs`

No documentation available.


### `Checker._get_full_cli_name`

No documentation available.


### `Checker._get_inputs`

No documentation available.


### `Checker._get_max_attempt`

No documentation available.


### `Checker._get_task_pid`

No documentation available.


### `Checker._get_upstreams`

No documentation available.


### `Checker._increase_attempt`

No documentation available.


### `Checker._is_done`

No documentation available.


### `Checker._is_last_attempt`

No documentation available.


### `Checker._lock_upstreams`

No documentation available.


### `Checker._loop_check`

No documentation available.


### `Checker._mark_awaited`

No documentation available.


### `Checker._mark_done`

No documentation available.


### `Checker._play_bell`

No documentation available.


### `Checker._print_result`

No documentation available.


### `Checker._propagate_execution_id`

No documentation available.


### `Checker._run_all`

No documentation available.


### `Checker._run_and_check_all`

No documentation available.


### `Checker._set_args`

No documentation available.


### `Checker._set_env_map`

No documentation available.


### `Checker._set_execution_id`

Set current task execution id.

This method is meant for internal use.

### `Checker._set_has_cli_interface`

No documentation available.


### `Checker._set_input_map`

No documentation available.


### `Checker._set_keyval`

No documentation available.


### `Checker._set_kwargs`

No documentation available.


### `Checker._set_local_keyval`

No documentation available.


### `Checker._set_task_pid`

No documentation available.


### `Checker._should_attempt`

No documentation available.


### `Checker._show_done_info`

No documentation available.


### `Checker._show_env_prefix`

No documentation available.


### `Checker._show_run_command`

No documentation available.


### `Checker._start_timer`

No documentation available.


### `Checker.add_env`

Add Env to the end of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `Checker.add_env_file`

Add EnvFile to the end of current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `Checker.add_input`

Add AnyInput to the end of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `Checker.add_upstream`

Add AnyTask to the end of the current task's upstream list.

### `Checker.check`

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

### `Checker.copy`

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

### `Checker.get_cli_name`

No documentation available.


### `Checker.get_color`

No documentation available.


### `Checker.get_description`

No documentation available.


### `Checker.get_env_map`

No documentation available.


### `Checker.get_execution_id`

No documentation available.


### `Checker.get_icon`

No documentation available.


### `Checker.get_input_map`

No documentation available.


### `Checker.inject_checkers`

No documentation available.


### `Checker.inject_env_files`

No documentation available.


### `Checker.inject_envs`

No documentation available.


### `Checker.inject_inputs`

No documentation available.


### `Checker.inject_upstreams`

No documentation available.


### `Checker.insert_env`

Insert Env to the beginning of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `Checker.insert_env_file`

Insert EnvFile to the beginning of the current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `Checker.insert_input`

Insert AnyInput to the beginning of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `Checker.insert_upstream`

Insert AnyTask to the beginning of the current task's upstream list.

### `Checker.inspect`

No documentation available.


### `Checker.log_critical`

No documentation available.


### `Checker.log_debug`

No documentation available.


### `Checker.log_error`

No documentation available.


### `Checker.log_info`

No documentation available.


### `Checker.log_warn`

No documentation available.


### `Checker.on_failed`

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

### `Checker.on_ready`

## Description

Define what to do when the current task status is `ready`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_ready(self):
self.print_out('The task is ready')
```

### `Checker.on_retry`

## Description

Define what to do when the current task status is `retry`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_retry(self):
self.print_out('The task is retrying')
```

### `Checker.on_skipped`

## Description

Define what to do when the current task status is `skipped`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_skipped(self):
self.print_out('The task is not started')
```

### `Checker.on_started`

## Description

Define what to do when the current task status is `started`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_started(self):
self.print_out('The task is started')
```

### `Checker.on_triggered`

## Description

Define what to do when the current task status is `triggered`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_triggered(self):
self.print_out('The task has been triggered')
```

### `Checker.on_waiting`

## Description

Define what to do when the current task status is `waiting`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_waiting(self):
self.print_out('The task is waiting to be started')
```

### `Checker.print_err`

No documentation available.


### `Checker.print_out`

No documentation available.


### `Checker.print_out_dark`

No documentation available.


### `Checker.print_result`

Print result to stdout so that it can be processed further.
e.g.: echo $(zrb explain solid) > solid-principle.txt

You need to override this method
if you want to show the result differently.

### `Checker.render_any`

No documentation available.


### `Checker.render_bool`

No documentation available.


### `Checker.render_file`

No documentation available.


### `Checker.render_float`

No documentation available.


### `Checker.render_int`

No documentation available.


### `Checker.render_str`

No documentation available.


### `Checker.run`

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

### `Checker.set_checking_interval`

No documentation available.


### `Checker.set_color`

No documentation available.


### `Checker.set_description`

Set current task description.
Usually used to overide copied task's description.

### `Checker.set_icon`

Set current task icon.
Usually used to overide copied task's icon.

### `Checker.set_name`

Set current task name.
Usually used to overide copied task's name.

### `Checker.set_retry`

No documentation available.


### `Checker.set_retry_interval`

No documentation available.


### `Checker.set_should_execute`

No documentation available.


### `Checker.show_progress`

No documentation available.


### `Checker.to_function`

Turn current task into a callable.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)