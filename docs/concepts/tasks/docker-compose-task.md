🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# DockerComposeTask

Docker Compose is a convenient way to run containers on your local computer.

Suppose you have the following Docker Compose file:

```yaml
# docker-compose.yml file
version: '3'

services:
  # The load balancer
  nginx:
    image: nginx:1.16.0-alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "${HOST_PORT:-8080}:80"
```

You can define a task to run your Docker Compose file (i.e., `docker compose up`) like this:

```python
from zrb import DockerComposeTask, HTTPChecker, Env, runner

run_container = DockerComposeTask(
    name='run-container',
    compose_cmd='up',
    compose_file='docker-compose.yml',
    envs=[
        Env(name='HOST_PORT', default='3000')
    ],
    checkers=[
        HTTPChecker(
            name='check-readiness', port='{{env.HOST_PORT}}'
        )
    ]
)
runner.register(run_container)
```

You can then run the task by invoking:

```bash
zrb run-container
```

Under the hood, Zrb will read your `compose_file` populate it with some additional configuration, and create a runtime compose file `._<compose-file>-<task-name>.runtime.yml`. Zrb will use the run the runtime compose file to run your `compose_cmd` (i.e., `docker compose -f <compose-file>-<task-name>.runtime.yml <compose-cmd>`)


# Technical Documentation

<!--start-doc-->
## `DockerComposeTask`

Command Task.
You can use this task to run shell command.

For example:
```python
# run a simple task
hello = CmdTask(
name='hello',
inputs=[StrInput(name='name', default='World')],
envs=[Env(name='HOME_DIR', os_name='HOME')],
cmd=[
'echo Hello {{ input.name }}',
'echo Home directory is: $HOME_DIR',
]
)
runner.register(hello)

# run a long running process
run_server = CmdTask(
name='run',
inputs=[StrInput(name='dir', default='.')],
envs=[Env(name='PORT', os_name='WEB_PORT', default='3000')],
cmd='python -m http.server $PORT --directory {{input.dir}}',
checkers=[HTTPChecker(port='{{env.PORT}}')]
)
runner.register(run_server)
```

### `DockerComposeTask._BaseTaskModel__get_colored`

No documentation available.


### `DockerComposeTask._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `DockerComposeTask._BaseTaskModel__get_common_prefix`

No documentation available.


### `DockerComposeTask._BaseTaskModel__get_executable_name`

No documentation available.


### `DockerComposeTask._BaseTaskModel__get_log_prefix`

No documentation available.


### `DockerComposeTask._BaseTaskModel__get_print_prefix`

No documentation available.


### `DockerComposeTask._BaseTaskModel__get_rjust_full_cli_name`

No documentation available.


### `DockerComposeTask._CmdTask__add_to_buffer`

No documentation available.


### `DockerComposeTask._CmdTask__get_multiline_repr`

No documentation available.


### `DockerComposeTask._CmdTask__get_rendered_cmd`

No documentation available.


### `DockerComposeTask._CmdTask__get_rendered_cmd_path`

No documentation available.


### `DockerComposeTask._CmdTask__is_process_exist`

No documentation available.


### `DockerComposeTask._CmdTask__kill_by_pid`

Kill a pid, gracefully

### `DockerComposeTask._CmdTask__log_from_queue`

No documentation available.


### `DockerComposeTask._CmdTask__on_exit`

No documentation available.


### `DockerComposeTask._CmdTask__on_kill`

No documentation available.


### `DockerComposeTask._CmdTask__queue_stream`

No documentation available.


### `DockerComposeTask._CmdTask__set_cwd`

No documentation available.


### `DockerComposeTask._CmdTask__wait_process`

No documentation available.


### `DockerComposeTask._DockerComposeTask__apply_service_env`

No documentation available.


### `DockerComposeTask._DockerComposeTask__generate_compose_runtime_file`

No documentation available.


### `DockerComposeTask._DockerComposeTask__get_compose_runtime_file`

No documentation available.


### `DockerComposeTask._DockerComposeTask__get_compose_template_file`

No documentation available.


### `DockerComposeTask._DockerComposeTask__get_env_compose_value`

No documentation available.


### `DockerComposeTask._DockerComposeTask__get_service_new_env_list`

No documentation available.


### `DockerComposeTask._DockerComposeTask__get_service_new_env_map`

No documentation available.


### `DockerComposeTask._Renderer__ensure_cached_render_data`

No documentation available.


### `DockerComposeTask._Renderer__get_render_data`

No documentation available.


### `DockerComposeTask._cached_check`

No documentation available.


### `DockerComposeTask._cached_run`

No documentation available.


### `DockerComposeTask._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `DockerComposeTask._check_should_execute`

No documentation available.


### `DockerComposeTask._create_cmd_script`

No documentation available.


### `DockerComposeTask._end_timer`

No documentation available.


### `DockerComposeTask._get_attempt`

No documentation available.


### `DockerComposeTask._get_checkers`

No documentation available.


### `DockerComposeTask._get_combined_env`

No documentation available.


### `DockerComposeTask._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `DockerComposeTask._get_elapsed_time`

No documentation available.


### `DockerComposeTask._get_env_files`

No documentation available.


### `DockerComposeTask._get_envs`

No documentation available.


### `DockerComposeTask._get_full_cli_name`

No documentation available.


### `DockerComposeTask._get_inputs`

No documentation available.


### `DockerComposeTask._get_max_attempt`

No documentation available.


### `DockerComposeTask._get_task_pid`

No documentation available.


### `DockerComposeTask._get_upstreams`

No documentation available.


### `DockerComposeTask._increase_attempt`

No documentation available.


### `DockerComposeTask._is_done`

No documentation available.


### `DockerComposeTask._is_last_attempt`

No documentation available.


### `DockerComposeTask._lock_upstreams`

No documentation available.


### `DockerComposeTask._loop_check`

No documentation available.


### `DockerComposeTask._mark_awaited`

No documentation available.


### `DockerComposeTask._mark_done`

No documentation available.


### `DockerComposeTask._play_bell`

No documentation available.


### `DockerComposeTask._print_result`

No documentation available.


### `DockerComposeTask._propagate_execution_id`

No documentation available.


### `DockerComposeTask._run_all`

No documentation available.


### `DockerComposeTask._run_and_check_all`

No documentation available.


### `DockerComposeTask._set_args`

No documentation available.


### `DockerComposeTask._set_env_map`

No documentation available.


### `DockerComposeTask._set_execution_id`

Set current task execution id.

This method is meant for internal use.

### `DockerComposeTask._set_has_cli_interface`

No documentation available.


### `DockerComposeTask._set_input_map`

No documentation available.


### `DockerComposeTask._set_keyval`

No documentation available.


### `DockerComposeTask._set_kwargs`

No documentation available.


### `DockerComposeTask._set_local_keyval`

No documentation available.


### `DockerComposeTask._set_task_pid`

No documentation available.


### `DockerComposeTask._should_attempt`

No documentation available.


### `DockerComposeTask._show_done_info`

No documentation available.


### `DockerComposeTask._show_env_prefix`

No documentation available.


### `DockerComposeTask._show_run_command`

No documentation available.


### `DockerComposeTask._start_timer`

No documentation available.


### `DockerComposeTask.add_env`

Add Env to the end of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `DockerComposeTask.add_env_file`

Add EnvFile to the end of current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `DockerComposeTask.add_input`

Add AnyInput to the end of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `DockerComposeTask.add_upstream`

Add AnyTask to the end of the current task's upstream list.

### `DockerComposeTask.check`

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

### `DockerComposeTask.copy`

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

### `DockerComposeTask.get_cli_name`

No documentation available.


### `DockerComposeTask.get_cmd_script`

No documentation available.


### `DockerComposeTask.get_color`

No documentation available.


### `DockerComposeTask.get_description`

No documentation available.


### `DockerComposeTask.get_env_map`

No documentation available.


### `DockerComposeTask.get_execution_id`

No documentation available.


### `DockerComposeTask.get_icon`

No documentation available.


### `DockerComposeTask.get_input_map`

No documentation available.


### `DockerComposeTask.inject_checkers`

No documentation available.


### `DockerComposeTask.inject_env_files`

No documentation available.


### `DockerComposeTask.inject_envs`

No documentation available.


### `DockerComposeTask.inject_inputs`

No documentation available.


### `DockerComposeTask.inject_upstreams`

No documentation available.


### `DockerComposeTask.insert_env`

Insert Env to the beginning of the current task's env list.
If there are two Env with the same name, the later will override the first ones.

### `DockerComposeTask.insert_env_file`

Insert EnvFile to the beginning of the current task's env_file list.
If there are two EnvFile with the same name, the later will override the first ones.

### `DockerComposeTask.insert_input`

Insert AnyInput to the beginning of the current task's input list.
If there are two input with the same name, the later will override the first ones.

### `DockerComposeTask.insert_upstream`

Insert AnyTask to the beginning of the current task's upstream list.

### `DockerComposeTask.log_critical`

No documentation available.


### `DockerComposeTask.log_debug`

No documentation available.


### `DockerComposeTask.log_error`

No documentation available.


### `DockerComposeTask.log_info`

No documentation available.


### `DockerComposeTask.log_warn`

No documentation available.


### `DockerComposeTask.on_failed`

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

### `DockerComposeTask.on_ready`

## Description

Define what to do when the current task status is `ready`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_ready(self):
self.print_out('The task is ready')
```

### `DockerComposeTask.on_retry`

## Description

Define what to do when the current task status is `retry`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_retry(self):
self.print_out('The task is retrying')
```

### `DockerComposeTask.on_skipped`

## Description

Define what to do when the current task status is `skipped`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_skipped(self):
self.print_out('The task is not started')
```

### `DockerComposeTask.on_started`

## Description

Define what to do when the current task status is `started`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_started(self):
self.print_out('The task is started')
```

### `DockerComposeTask.on_triggered`

## Description

Define what to do when the current task status is `triggered`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_triggered(self):
self.print_out('The task has been triggered')
```

### `DockerComposeTask.on_waiting`

## Description

Define what to do when the current task status is `waiting`.

You can override this method.

## Example

```python
class MyTask(Task):
async def on_waiting(self):
self.print_out('The task is waiting to be started')
```

### `DockerComposeTask.print_err`

No documentation available.


### `DockerComposeTask.print_out`

No documentation available.


### `DockerComposeTask.print_out_dark`

No documentation available.


### `DockerComposeTask.print_result`

Print result to stdout so that it can be processed further.
e.g.: echo $(zrb explain solid) > solid-principle.txt

You need to override this method
if you want to show the result differently.

### `DockerComposeTask.render_any`

No documentation available.


### `DockerComposeTask.render_bool`

No documentation available.


### `DockerComposeTask.render_file`

No documentation available.


### `DockerComposeTask.render_float`

No documentation available.


### `DockerComposeTask.render_int`

No documentation available.


### `DockerComposeTask.render_str`

No documentation available.


### `DockerComposeTask.run`

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

### `DockerComposeTask.set_checking_interval`

No documentation available.


### `DockerComposeTask.set_color`

No documentation available.


### `DockerComposeTask.set_cwd`

No documentation available.


### `DockerComposeTask.set_description`

Set current task description.
Usually used to overide copied task's description.

### `DockerComposeTask.set_icon`

Set current task icon.
Usually used to overide copied task's icon.

### `DockerComposeTask.set_name`

Set current task name.
Usually used to overide copied task's name.

### `DockerComposeTask.set_retry`

No documentation available.


### `DockerComposeTask.set_retry_interval`

No documentation available.


### `DockerComposeTask.set_should_execute`

No documentation available.


### `DockerComposeTask.to_function`

Turn current task into a callable.

<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)