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

For internal use

### `DockerComposeTask._mark_awaited`

No documentation available.


### `DockerComposeTask._mark_done`

No documentation available.


### `DockerComposeTask._play_bell`

No documentation available.


### `DockerComposeTask._print_result`

For internal use

### `DockerComposeTask._propagate_execution_id`

No documentation available.


### `DockerComposeTask._run_all`

For internal use

### `DockerComposeTask._run_and_check_all`

No documentation available.


### `DockerComposeTask._set_args`

No documentation available.


### `DockerComposeTask._set_env_map`

No documentation available.


### `DockerComposeTask._set_execution_id`

Sets the execution ID for the current task.

This method is intended for internal use to assign a unique identifier to the task's execution.
This ID can be used for tracking, logging, and inter-task communication.

This method should not be used externally, as it is meant to be managed within the task system.

__Arguments:__

- `execution_id` (`str`): A string representing the unique execution ID.

### `DockerComposeTask._set_has_cli_interface`

No documentation available.


### `DockerComposeTask._set_input_map`

No documentation available.


### `DockerComposeTask._set_keyval`

For internal use

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

Adds one or more `Env` instances to the end of the current task's environment variable list.

Use this method to append environment variables for the task, which will be used after
any variables already set.

__Arguments:__

- `envs` (`Env`): One or more environment variable instances to be added.

Example:
```python
from zrb import Task, Env
task = Task(name='task')
db_url_env = Env(name='DATABASE_URL', value='postgresql://...')
task.add_env(env_var)
```


### `DockerComposeTask.add_env_file`

Adds one or more `EnvFile` instances to the end of the current task's environment file list.

Use this method to append environment file references, which will be processed after
any files already specified. This allows for supplementing the existing environment
configuration.

__Arguments:__

- `env_files` (`EnvFile`): One or more environment file instances to be added.

Example:
```python
from zrb import Task, EnvFile
task = Task()
env_file = EnvFile(env_file='config.env')
task.add_env_file(env_file)
```


### `DockerComposeTask.add_input`

Adds one or more `AnyInput` instances to the end of the current task's input list.

This method is used to append inputs for the task to process, placing them after any inputs
already specified.

__Arguments:__

- `inputs` (`AnyInput`): One or more input instances to be added to the input list.

Example:
```python
from zrb import Task, Input
task = Task(name='task')
email_input = Input(name='email-address')
task.add_input(email_input)
```


### `DockerComposeTask.add_upstream`

Adds one or more `AnyTask` instances to the end of the current task's upstream list.

This method appends tasks to the upstream list, indicating that these tasks should be executed
before the current task, but after any tasks already in the upstream list.

__Arguments:__

- `upstreams` (`TAnyTask`): One or more task instances to be added to the upstream list.

Example:
```python
from zrb import Task
task = Task(name='task')
upstream_task = Task(name='upstream-task')
task.add_upstream(upstream_task)
```


### `DockerComposeTask.check`

Checks if the current task is `ready`.

Any other tasks depends on the current task, will be `started` once the current task is `ready`.

This method should be implemented to define the criteria for considering the task
`ready`. The specifics of this completion depend on the task's
nature and the subclass implementation.

__Returns:__

`bool`: True if the task is completed, False otherwise.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def run(self, *args: Any, **kwargs: Any) -> int:
        self.print_out('Doing some calculation')
        self._completed = True
        return 42
    async def check(self) -> bool:
        return self._completed
```


### `DockerComposeTask.copy`

Creates and returns a copy of the current task.

The copied task can be modified using various setter methods like `set_name`,
`set_description`, and others, depending on the subclass implementation.

__Returns:__

`TAnyTask`: A copy of the current task.

Example:
```python
from zrb import Task
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

Inserts one or more `Env` instances at the beginning of the current task's environment variable list.

This method allows for setting or overriding environment variables for the task, with earlier entries
having precedence over later ones.

__Arguments:__

- `envs` (`Env`): One or more environment variable instances to be added.

Example:
```python
from zrb import Task, Env
task = Task(name='task')
db_url_env = Env(name='DATABASE_URL', value='postgresql://...')
task.insert_env(env_var)
```


### `DockerComposeTask.insert_env_file`

Inserts one or more `EnvFile` instances at the beginning of the current task's environment file list.

This method is used to specify environment variable files whose contents should be loaded
before those of any files already in the list. This is useful for overriding or setting
additional environment configurations.

__Arguments:__

- `env_files` (`EnvFile`): One or more environment file instances to be added.

Example:
```python
from zrb import Task, EnvFile
task = Task()
env_file = EnvFile(env_file='config.env')
task.insert_env_file(env_file)
```


### `DockerComposeTask.insert_input`

Inserts one or more `AnyInput` instances at the beginning of the current task's input list.

This method is used to add inputs that the task will process. Inserting an input at the beginning
of the list gives it precedence over those already present.

__Arguments:__

- `inputs` (`AnyInput`): One or more input instances to be added to the input list.

Example:
```python
from zrb import Task, Input
task = Task(name='task')
email_input = Input(name='email-address')
task.insert_input(email_input)
```


### `DockerComposeTask.insert_upstream`

Inserts one or more `AnyTask` instances at the beginning of the current task's upstream list.

This method is used to define dependencies for the current task. Tasks in the upstream list are
executed before the current task. Adding a task to the beginning of the list means it will be
executed earlier than those already in the list.

__Arguments:__

- `upstreams` (`TAnyTask`): One or more task instances to be added to the upstream list.

Example:
```python
from zrb import Task
task = Task(name='task')
upstream_task = Task(name='upstream-task')
task.insert_upstream(upstream_task)
```


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

Specifies the behavior when the task execution fails.

This asynchronous method should be implemented in subclasses to handle task
failure scenarios. It can include logging the error, performing retries, or
any other failure handling mechanisms.

__Arguments:__

- `is_last_attempt` (`bool`): Indicates if this is the final retry attempt.
- `exception` (`Exception`): The exception that caused the task to fail.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def on_failed(self, is_last_attempt: bool, exception: Exception):
        if is_last_attempt:
            self.print_out('The task has failed with no remaining retries')
        else:
            self.print_out('The task failed, retrying...')
```


### `DockerComposeTask.on_ready`

Defines actions to be performed when the task status is `ready`.

This asynchronous method should be implemented in subclasses to specify
actions that occur when the task reaches the `ready` state. This can include
any cleanup, notification, or follow-up actions specific to the task.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def on_ready(self):
        self.print_out('The task is ready')
```


### `DockerComposeTask.on_retry`

Defines actions to perform when the task is retried.

Implement this method to specify behavior when the task is retried after a failure.
This could include resetting states, logging the retry attempt, or other necessary
steps before re-execution.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def on_retry(self):
        self.log_info('Retrying task')
```


### `DockerComposeTask.on_skipped`

Defines actions to perform when the task status is set to `skipped`.

Implement this method to specify behavior when the task is skipped. This could
include logging information, cleaning up resources, or any other necessary steps.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def on_skipped(self):
        self.log_info('Task was skipped')
```


### `DockerComposeTask.on_started`

Defines actions to perform when the task status is set to 'started'.

Implement this method to specify behavior when the task starts its execution. This
could involve initializing resources, logging, or other startup procedures.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def on_started(self):
        self.log_info('Task has started')
```


### `DockerComposeTask.on_triggered`

Defines actions to perform when the task status is set to `triggered`.

Implement this method to specify behavior when the task transitions to the
`triggered` state. This could involve setting up prerequisites or sending
notifications.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def on_triggered(self):
        self.log_info('Task has been triggered')
```


### `DockerComposeTask.on_waiting`

Defines actions to perform when the task status is set to `waiting`.

Implement this method to specify behavior when the task transitions to the
`waiting` state. This state usually indicates the task is waiting for some
condition or prerequisite to be met.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def on_waiting(self):
        self.log_info('Task is waiting to be started')
```


### `DockerComposeTask.print_err`

No documentation available.


### `DockerComposeTask.print_out`

No documentation available.


### `DockerComposeTask.print_out_dark`

No documentation available.


### `DockerComposeTask.print_result`

Outputs the task result to stdout for further processing.

Override this method in subclasses to customize how the task result is displayed
or processed. Useful for integrating the task output with other systems or
command-line tools.

__Arguments:__

- `result` (`Any`): The result of the task to be printed.

Example:
>> from zrb import Task
>> # Example of overriding in a subclass
>> class MyTask(Task):
>>    def print_result(self, result: Any):
>>        print(f'Result: {result}')

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

Executes the main logic of the task.

This asynchronous method should be implemented in subclasses to define the
task's primary functionality. The specific behavior and the return value
depend on the task's nature and purpose.

__Arguments:__

- `args` (`Any`): Variable length argument list.
- `kwargs` (`Any`): Arbitrary keyword arguments.

__Returns:__

`Any`: The result of the task execution, the type of which is determined by
the specific task implementation.

Example:
```python
from zrb import Task
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

Converts the current task into a callable function.

This method should be implemented to allow the task to be executed as a function.
Parameters can be used to modify the behavior of the generated function, such as
raising errors, asynchronous execution, and logging.

__Arguments:__

- `env_prefix` (`str`): A prefix for environment variables.
- `raise_error` (`bool`): Whether to raise an error if the task execution fails.
- `is_async` (`bool`): Whether the resulting function should be asynchronous.
- `show_done_info` (`bool`): Whether to show information upon task completion.

__Returns:__

`Callable[..., Any]`: A callable representation of the task.

Example:
```python
from zrb import Task
class MyTask(Task):
    async def run(self, *args: Any, **kwargs: Any) -> int:
        self.print_out('Doing some calculation')
        return 42
````

>>>
```python
task = MyTask()
fn = task.to_function()
fn()
```


<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)