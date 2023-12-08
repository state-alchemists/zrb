🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# CmdTask

You can use CmdTask to run CLI commands.

Let's see the following example:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd='echo {{input.name}}'
)
runner.register(say_hello)
```

If you need a multi-line command, you can also define the command as a list:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd=[
        'echo {{input.name}}',
        'echo $_INPUT_NAME', # This will also works
        'echo Yeay!!!'
    ]
)
runner.register(say_hello)
```

However, if your command is too long, you can also load it from another file:


```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd_path='hello_script.sh'
)
runner.register(say_hello)
```

You can then run the task by invoking:

```bash
zrb say-hello --name=John
```

# Technical Documentation

<!--start-doc-->
## `CmdTask`

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

### `CmdTask._BaseTaskModel__get_colored`

No documentation available.


### `CmdTask._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `CmdTask._BaseTaskModel__get_common_prefix`

No documentation available.


### `CmdTask._BaseTaskModel__get_executable_name`

No documentation available.


### `CmdTask._BaseTaskModel__get_log_prefix`

No documentation available.


### `CmdTask._BaseTaskModel__get_print_prefix`

No documentation available.


### `CmdTask._BaseTaskModel__get_rjust_full_cli_name`

No documentation available.


### `CmdTask._CmdTask__add_to_buffer`

No documentation available.


### `CmdTask._CmdTask__get_multiline_repr`

No documentation available.


### `CmdTask._CmdTask__get_rendered_cmd`

No documentation available.


### `CmdTask._CmdTask__get_rendered_cmd_path`

No documentation available.


### `CmdTask._CmdTask__is_process_exist`

No documentation available.


### `CmdTask._CmdTask__kill_by_pid`

Kill a pid, gracefully

### `CmdTask._CmdTask__log_from_queue`

No documentation available.


### `CmdTask._CmdTask__on_exit`

No documentation available.


### `CmdTask._CmdTask__on_kill`

No documentation available.


### `CmdTask._CmdTask__queue_stream`

No documentation available.


### `CmdTask._CmdTask__set_cwd`

No documentation available.


### `CmdTask._CmdTask__wait_process`

No documentation available.


### `CmdTask._Renderer__ensure_cached_render_data`

No documentation available.


### `CmdTask._Renderer__get_render_data`

No documentation available.


### `CmdTask._cached_check`

No documentation available.


### `CmdTask._cached_run`

No documentation available.


### `CmdTask._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `CmdTask._check_should_execute`

No documentation available.


### `CmdTask._create_cmd_script`

No documentation available.


### `CmdTask._end_timer`

No documentation available.


### `CmdTask._get_attempt`

No documentation available.


### `CmdTask._get_checkers`

No documentation available.


### `CmdTask._get_combined_env`

No documentation available.


### `CmdTask._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `CmdTask._get_elapsed_time`

No documentation available.


### `CmdTask._get_env_files`

No documentation available.


### `CmdTask._get_envs`

No documentation available.


### `CmdTask._get_full_cli_name`

No documentation available.


### `CmdTask._get_inputs`

No documentation available.


### `CmdTask._get_max_attempt`

No documentation available.


### `CmdTask._get_task_pid`

No documentation available.


### `CmdTask._get_upstreams`

No documentation available.


### `CmdTask._increase_attempt`

No documentation available.


### `CmdTask._is_done`

No documentation available.


### `CmdTask._is_last_attempt`

No documentation available.


### `CmdTask._lock_upstreams`

No documentation available.


### `CmdTask._loop_check`

For internal use

### `CmdTask._mark_awaited`

No documentation available.


### `CmdTask._mark_done`

No documentation available.


### `CmdTask._play_bell`

No documentation available.


### `CmdTask._print_result`

For internal use

### `CmdTask._propagate_execution_id`

No documentation available.


### `CmdTask._run_all`

For internal use

### `CmdTask._run_and_check_all`

No documentation available.


### `CmdTask._set_args`

No documentation available.


### `CmdTask._set_env_map`

No documentation available.


### `CmdTask._set_execution_id`

Sets the execution ID for the current task.

This method is intended for internal use to assign a unique identifier to the task's execution.
This ID can be used for tracking, logging, and inter-task communication.

This method should not be used externally, as it is meant to be managed within the task system.

__Arguments:__

- `execution_id` (`str`): A string representing the unique execution ID.

### `CmdTask._set_has_cli_interface`

No documentation available.


### `CmdTask._set_input_map`

No documentation available.


### `CmdTask._set_keyval`

For internal use

### `CmdTask._set_kwargs`

No documentation available.


### `CmdTask._set_local_keyval`

No documentation available.


### `CmdTask._set_task_pid`

No documentation available.


### `CmdTask._should_attempt`

No documentation available.


### `CmdTask._show_done_info`

No documentation available.


### `CmdTask._show_env_prefix`

No documentation available.


### `CmdTask._show_run_command`

No documentation available.


### `CmdTask._start_timer`

No documentation available.


### `CmdTask.add_env`

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


### `CmdTask.add_env_file`

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


### `CmdTask.add_input`

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


### `CmdTask.add_upstream`

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


### `CmdTask.check`

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


### `CmdTask.copy`

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


### `CmdTask.get_cli_name`

No documentation available.


### `CmdTask.get_cmd_script`

No documentation available.


### `CmdTask.get_color`

No documentation available.


### `CmdTask.get_description`

No documentation available.


### `CmdTask.get_env_map`

No documentation available.


### `CmdTask.get_execution_id`

Retrieves the execution ID of the task.

This method returns the unique identifier associated with the task's execution.
The execution ID is crucial for tracking, logging, and differentiating between
multiple instances or runs of the same task.

__Returns:__

`str`: The unique execution ID of the task.

### `CmdTask.get_icon`

No documentation available.


### `CmdTask.get_input_map`

No documentation available.


### `CmdTask.inject_checkers`

No documentation available.


### `CmdTask.inject_env_files`

No documentation available.


### `CmdTask.inject_envs`

No documentation available.


### `CmdTask.inject_inputs`

No documentation available.


### `CmdTask.inject_upstreams`

No documentation available.


### `CmdTask.insert_env`

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


### `CmdTask.insert_env_file`

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


### `CmdTask.insert_input`

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


### `CmdTask.insert_upstream`

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


### `CmdTask.log_critical`

No documentation available.


### `CmdTask.log_debug`

No documentation available.


### `CmdTask.log_error`

No documentation available.


### `CmdTask.log_info`

No documentation available.


### `CmdTask.log_warn`

No documentation available.


### `CmdTask.on_failed`

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


### `CmdTask.on_ready`

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


### `CmdTask.on_retry`

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


### `CmdTask.on_skipped`

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


### `CmdTask.on_started`

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


### `CmdTask.on_triggered`

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


### `CmdTask.on_waiting`

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


### `CmdTask.print_err`

No documentation available.


### `CmdTask.print_out`

No documentation available.


### `CmdTask.print_out_dark`

No documentation available.


### `CmdTask.print_result`

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

### `CmdTask.render_any`

No documentation available.


### `CmdTask.render_bool`

No documentation available.


### `CmdTask.render_file`

No documentation available.


### `CmdTask.render_float`

No documentation available.


### `CmdTask.render_int`

No documentation available.


### `CmdTask.render_str`

No documentation available.


### `CmdTask.run`

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


### `CmdTask.set_checking_interval`

Sets the interval for checking the task's readiness or completion status.

This method defines how frequently the system should check if the task is ready or completed.
It's useful for tasks that have an indeterminate completion time.

__Arguments:__

- `new_checking_interval` (`Union[float, int]`): The time interval (in seconds) for readiness or checks.

### `CmdTask.set_color`

Defines a new color for the current task.

This method updates the color associated with the task. This can be useful for categorization,
priority indication, or visual differentiation in a UI.

__Arguments:__

- `new_color` (`str`): A string representing the color to be assigned to the task.

### `CmdTask.set_cwd`

No documentation available.


### `CmdTask.set_description`

Sets a new description for the current task.

This method allows updating the task's description to provide more context or details about its purpose and behavior.
Useful for enhancing clarity and maintainability in the task management system.

__Arguments:__

- `new_description` (`str`): A string representing the new description of the task.

### `CmdTask.set_icon`

Assigns a new icon to the current task.

This method is used for setting or updating the task's icon, which can be utilized for visual representation
in a user interface. The icon should ideally be a string identifier that maps to an actual graphical resource.

__Arguments:__

- `new_icon` (`str`): A string representing the icon identifier for the task.

### `CmdTask.set_name`

Sets a new name for the current task.

This method is used to update the task's name, typically after creating a copy of an existing task.
The new name helps in differentiating the task in the task management system.

__Arguments:__

- `new_name` (`str`): A string representing the new name to be assigned to the task.

### `CmdTask.set_retry`

Sets the number of retry attempts for the task.

This method configures how many times the task should be retried in case of failure.
It's essential for tasks that may fail transiently and need multiple attempts for successful execution.

__Arguments:__

- `new_retry` (`int`): An integer representing the number of retry attempts.

### `CmdTask.set_retry_interval`

Specifies the interval between retry attempts for the task.

This method sets the duration to wait before retrying the task after a failure.
This can help in scenarios where immediate retry is not desirable or effective.

__Arguments:__

- `new_retry_interval` (`Union[float, int]`): The time interval (in seconds) to wait before a retry attempt.

### `CmdTask.set_should_execute`

Determines whether the task should execute.

This method configures the execution criteria for the task. It can be set as a boolean value,
a string representing a condition, or a callable that returns a boolean. This is useful for
conditional task execution based on dynamic criteria.

__Arguments:__

- `should_execute` (`Union[bool, str, Callable[..., bool]]`): The condition to determine if the task should execute.

### `CmdTask.to_function`

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
