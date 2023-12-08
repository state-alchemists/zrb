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

For internal use

### `RemoteCmdTask._mark_awaited`

No documentation available.


### `RemoteCmdTask._mark_done`

No documentation available.


### `RemoteCmdTask._play_bell`

No documentation available.


### `RemoteCmdTask._print_result`

For internal use

### `RemoteCmdTask._propagate_execution_id`

No documentation available.


### `RemoteCmdTask._run_all`

For internal use

### `RemoteCmdTask._run_and_check_all`

No documentation available.


### `RemoteCmdTask._set_args`

No documentation available.


### `RemoteCmdTask._set_env_map`

No documentation available.


### `RemoteCmdTask._set_execution_id`

Sets the execution ID for the current task.

This method is intended for internal use to assign a unique identifier to the task's execution.
This ID can be used for tracking, logging, and inter-task communication.

This method should not be used externally, as it is meant to be managed within the task system.

__Arguments:__

- `execution_id` (`str`): A string representing the unique execution ID.

### `RemoteCmdTask._set_has_cli_interface`

No documentation available.


### `RemoteCmdTask._set_input_map`

No documentation available.


### `RemoteCmdTask._set_keyval`

For internal use

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


### `RemoteCmdTask.add_env_file`

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
env_file = EnvFile(path='config.env')
task.add_env_file(env_file)
```


### `RemoteCmdTask.add_input`

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


### `RemoteCmdTask.add_upstream`

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


### `RemoteCmdTask.check`

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


### `RemoteCmdTask.copy`

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


### `RemoteCmdTask.insert_env_file`

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
env_file = EnvFile(path='config.env')
task.insert_env_file(env_file)
```


### `RemoteCmdTask.insert_input`

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


### `RemoteCmdTask.insert_upstream`

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


### `RemoteCmdTask.on_ready`

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


### `RemoteCmdTask.on_retry`

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


### `RemoteCmdTask.on_skipped`

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


### `RemoteCmdTask.on_started`

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


### `RemoteCmdTask.on_triggered`

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


### `RemoteCmdTask.on_waiting`

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


### `RemoteCmdTask.print_err`

No documentation available.


### `RemoteCmdTask.print_out`

No documentation available.


### `RemoteCmdTask.print_out_dark`

No documentation available.


### `RemoteCmdTask.print_result`

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
