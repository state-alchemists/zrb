🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task](./README.md)

# BaseRemoteCmdTask

# Technical Specification

<!--start-doc-->
## `BaseRemoteCmdTask`

Base class for all tasks.
Every task definition should be extended from this class.

### `BaseRemoteCmdTask._BaseTaskModel__get_colored`

No documentation available.


### `BaseRemoteCmdTask._BaseTaskModel__get_colored_print_prefix`

No documentation available.


### `BaseRemoteCmdTask._BaseTaskModel__get_common_prefix`

No documentation available.


### `BaseRemoteCmdTask._BaseTaskModel__get_log_prefix`

No documentation available.


### `BaseRemoteCmdTask._BaseTaskModel__get_print_prefix`

No documentation available.


### `BaseRemoteCmdTask._Renderer__ensure_cached_render_data`

No documentation available.


### `BaseRemoteCmdTask._Renderer__get_render_data`

No documentation available.


### `BaseRemoteCmdTask._cached_check`

No documentation available.


### `BaseRemoteCmdTask._cached_run`

No documentation available.


### `BaseRemoteCmdTask._check`

Check current task readiness.
- If self.checkers is defined,
this will return True once every self.checkers is completed
- Otherwise, this will return check method's return value.

### `BaseRemoteCmdTask._check_should_execute`

No documentation available.


### `BaseRemoteCmdTask._end_timer`

No documentation available.


### `BaseRemoteCmdTask._get_attempt`

No documentation available.


### `BaseRemoteCmdTask._get_checkers`

Retrieves the checkers set for the task.

This internal method returns an iterable of all the checkers that have been added to
the task. It's mainly used for internal logic and debugging to understand the
validations or conditions applied to the task.

__Returns:__

`Iterable[TAnyTask]`: An iterable of checkers associated with the task.

### `BaseRemoteCmdTask._get_combined_env`

No documentation available.


### `BaseRemoteCmdTask._get_combined_inputs`

'
Getting all inputs of this task and all its upstream, non-duplicated.

### `BaseRemoteCmdTask._get_elapsed_time`

No documentation available.


### `BaseRemoteCmdTask._get_env_files`

Retrieves the list of environment variable files associated with the task.

Intended for internal use, this method returns a list of `EnvFile` instances that the task
uses to load environment variables, primarily for setup and configuration purposes.

__Returns:__

`List[EnvFile]`: A list of `EnvFile` instances associated with the task.

### `BaseRemoteCmdTask._get_envs`

Retrieves the list of environment variables set for the task.

For internal use, this method returns a list of `Env` instances representing the environment variables
configured for the task, essential for understanding and debugging the task's environment setup.

__Returns:__

`List[Env]`: A list of `Env` instances representing the environment variables of the task.

### `BaseRemoteCmdTask._get_inputs`

Retrieves the list of inputs associated with the task.

This internal method is used to obtain all the inputs that have been set for the task,
either through static definition or via the `inject_inputs` method. It's primarily used
for introspection and debugging purposes.

__Returns:__

`List[AnyInput]`: A list of `AnyInput` instances representing the inputs for the task.

### `BaseRemoteCmdTask._get_max_attempt`

No documentation available.


### `BaseRemoteCmdTask._get_task_pid`

No documentation available.


### `BaseRemoteCmdTask._get_upstreams`

Retrieves the upstream tasks of the current task.

An internal method to get the list of upstream tasks that have been set for the
task, either statically or through `inject_upstreams`. This is essential for task
scheduling and dependency management.

__Returns:__

`Iterable[TAnyTask]`: An iterable of upstream tasks.

### `BaseRemoteCmdTask._increase_attempt`

No documentation available.


### `BaseRemoteCmdTask._is_done`

No documentation available.


### `BaseRemoteCmdTask._is_last_attempt`

No documentation available.


### `BaseRemoteCmdTask._lock_upstreams`

No documentation available.


### `BaseRemoteCmdTask._loop_check`

For internal use.

Regularly check whether the task is ready or not.

### `BaseRemoteCmdTask._mark_awaited`

No documentation available.


### `BaseRemoteCmdTask._mark_done`

No documentation available.


### `BaseRemoteCmdTask._play_bell`

No documentation available.


### `BaseRemoteCmdTask._print_result`

For internal use.

Call `print_result` or print values based on result type and other conditions.

### `BaseRemoteCmdTask._propagate_execution_id`

No documentation available.


### `BaseRemoteCmdTask._run_all`

For internal use.

Run this task and all its upstreams.

### `BaseRemoteCmdTask._run_and_check_all`

No documentation available.


### `BaseRemoteCmdTask._set_args`

Set args that will be shown at the end of the execution

### `BaseRemoteCmdTask._set_env_map`

No documentation available.


### `BaseRemoteCmdTask._set_execution_id`

Sets the execution ID for the current task.

This method is intended for internal use to assign a unique identifier to the task's execution.
This ID can be used for tracking, logging, and inter-task communication.

This method should not be used externally, as it is meant to be managed within the task system.

__Arguments:__

- `execution_id` (`str`): A string representing the unique execution ID.

### `BaseRemoteCmdTask._set_has_cli_interface`

Marks the task as having a CLI interface.

This internal method is used to indicate that the task is accessible and executable through a CLI,
enabling the task system to appropriately handle its CLI interactions.

### `BaseRemoteCmdTask._set_input_map`

No documentation available.


### `BaseRemoteCmdTask._set_keyval`

For internal use.

Set current task's key values.

### `BaseRemoteCmdTask._set_kwargs`

Set kwargs that will be shown at the end of the execution

### `BaseRemoteCmdTask._set_local_keyval`

No documentation available.


### `BaseRemoteCmdTask._set_task`

No documentation available.


### `BaseRemoteCmdTask._set_task_pid`

No documentation available.


### `BaseRemoteCmdTask._should_attempt`

No documentation available.


### `BaseRemoteCmdTask._show_done_info`

No documentation available.


### `BaseRemoteCmdTask._show_env_prefix`

No documentation available.


### `BaseRemoteCmdTask._show_run_command`

No documentation available.


### `BaseRemoteCmdTask._start_timer`

No documentation available.


### `BaseRemoteCmdTask.add_checker`

Adds one or more `AnyTask` instances to the end of the current task's checker list.

This method appends tasks to the checker list, indicating that these tasks should be executed
before the current task, but after any tasks already in the checker list.

__Arguments:__

- `checkers` (`TAnyTask`): One or more task instances to be added to the checker list.

__Examples:__

```python
from zrb import Task
task = Task(name='task')
checker_task = Task(name='checker-task')
task.add_checker(checker_task)
```


### `BaseRemoteCmdTask.add_env`

Adds one or more `Env` instances to the end of the current task's environment variable list.

Use this method to append environment variables for the task, which will be used after
any variables already set.

__Arguments:__

- `envs` (`Env`): One or more environment variable instances to be added.

__Examples:__

```python
from zrb import Task, Env
task = Task(name='task')
db_url_env = Env(name='DATABASE_URL', value='postgresql://...')
task.add_env(env_var)
```


### `BaseRemoteCmdTask.add_env_file`

Adds one or more `EnvFile` instances to the end of the current task's environment file list.

Use this method to append environment file references, which will be processed after
any files already specified. This allows for supplementing the existing environment
configuration.

__Arguments:__

- `env_files` (`EnvFile`): One or more environment file instances to be added.

__Examples:__

```python
from zrb import Task, EnvFile
task = Task()
env_file = EnvFile(path='config.env')
task.add_env_file(env_file)
```


### `BaseRemoteCmdTask.add_input`

Adds one or more `AnyInput` instances to the end of the current task's input list.

This method is used to append inputs for the task to process, placing them after any inputs
already specified.

__Arguments:__

- `inputs` (`AnyInput`): One or more input instances to be added to the input list.

__Examples:__

```python
from zrb import Task, Input
task = Task(name='task')
email_input = Input(name='email-address')
task.add_input(email_input)
```


### `BaseRemoteCmdTask.add_upstream`

Adds one or more `AnyTask` instances to the end of the current task's upstream list.

This method appends tasks to the upstream list, indicating that these tasks should be executed
before the current task, but after any tasks already in the upstream list.

__Arguments:__

- `upstreams` (`TAnyTask`): One or more task instances to be added to the upstream list.

__Examples:__

```python
from zrb import Task
task = Task(name='task')
upstream_task = Task(name='upstream-task')
task.add_upstream(upstream_task)
```


### `BaseRemoteCmdTask.check`

Checks if the current task is `ready`.

Any other tasks depends on the current task, will be `started` once the current task is `ready`.

This method should be implemented to define the criteria for considering the task
`ready`. The specifics of this completion depend on the task's
nature and the subclass implementation.

__Returns:__

`bool`: True if the task is completed, False otherwise.

__Examples:__

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


### `BaseRemoteCmdTask.clear_xcom`

No documentation available.


### `BaseRemoteCmdTask.copy`

Creates and returns a copy of the current task.

The copied task can be modified using various setter methods like `set_name`,
`set_description`, and others, depending on the subclass implementation.

__Returns:__

`TAnyTask`: A copy of the current task.

__Examples:__

```python
from zrb import Task
task = Task(name='my-task', cmd='echo hello')
copied_task = task.copy()
copied_task.set_name('new_name')
```


### `BaseRemoteCmdTask.get_cli_name`

Gets the command-line interface (CLI) name of the task.

This method returns the name used to invoke the task via a CLI, facilitating integration with command-line tools
or scripts.

__Returns:__

`str`: The CLI name of the task.

### `BaseRemoteCmdTask.get_color`

Retrieves the color associated with the current task.

This method returns the color of the task, useful for visual differentiation, priority indication,
or categorization in user interfaces or documentation.

__Returns:__

`str`: A string representing the color assigned to the task.

### `BaseRemoteCmdTask.get_description`

Fetches the current description of the task.

This method is used to obtain the detailed description of the task, providing insights into its purpose,
functionality, and usage within the task management system.

__Returns:__

`str`: The description of the task.

### `BaseRemoteCmdTask.get_env_map`

Get a map representing task's Envs and EnvFiles

Typically used inside `run`, `check`, or in `@python_task` decorator

__Examples:__

```python
from zrb import python_task, Task, Env
@python_task(name='task', envs=[Env(name='DB_URL')])
def task(*args, **kwargs):
    task: Task = kwargs.get('_task')
    for key, value in task.get_env_map():
        task.print_out(f'{key}: {value}')
```


### `BaseRemoteCmdTask.get_execution_id`

Retrieves the execution ID of the task.

This method returns the unique identifier associated with the task's execution.
The execution ID is crucial for tracking, logging, and differentiating between
multiple instances or runs of the same task.

__Returns:__

`str`: The unique execution ID of the task.

### `BaseRemoteCmdTask.get_icon`

Retrieves the icon identifier of the current task.

This method is used to get the icon associated with the task, which can be utilized for
visual representation in user interfaces or documentation.

__Returns:__

`str`: A string representing the icon identifier for the task

### `BaseRemoteCmdTask.get_input_map`

Get a map representing task's Inputs.

Typically used inside `run`, `check`, or in `@python_task` decorator

__Examples:__

```python
from zrb import python_task, Task, Input
@python_task(name='task', inputs=[Input(name='name')])
def task(*args, **kwargs):
    task: Task = kwargs.get('_task')
    for key, value in task.get_input_map():
        task.print_out(f'{key}: {value}')
```


### `BaseRemoteCmdTask.get_name`

Get task name

__Returns:__

`str`: name of the task

### `BaseRemoteCmdTask.get_xcom`

Get xcom value for cross task communication.

Argss:
key (str): Xcom key

__Returns:__

`str`: Value of xcom

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def run(self, *args: Any, **kwargs: Any) -> int:
        return self.get_xcom('magic_word')
```


### `BaseRemoteCmdTask.inject_checkers`

Injects custom checkers into the task.

This method allows for the addition of custom validation or condition checkers. These
checkers can be used to verify certain conditions before the task execution proceeds.
Subclasses should implement this method to define task-specific checkers.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    def inject_checkers(self):
        self.add_checker(some_custom_condition_checker)
```


### `BaseRemoteCmdTask.inject_env_files`

Injects additional `EnvFile` into the task.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    def inject_env_files(self):
        self.add_env_files(EnvFile(path='config.env'))
```


### `BaseRemoteCmdTask.inject_envs`

Injects environment variables into the task.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    def inject_envs(self):
        self.add_envs(Env(name='DATABASE_URL'))
```


### `BaseRemoteCmdTask.inject_inputs`

Injects custom inputs into the task.

This method is used to programmatically add input parameters to the task, allowing
dynamic customization of the task's input data. Subclasses should override this method
to define specific inputs that the task should receive.

__Examples:__

```python
from zrb import Task, Input
class MyTask(Task):
    def inject_inputs(self):
        self.add_input(Input(name='user_email', type='email'))
```


### `BaseRemoteCmdTask.inject_upstreams`

Injects upstream tasks into the current task.

This method is used for programmatically adding upstream dependencies to the task.
Upstream tasks are those that must be completed before the current task starts.
Override this method in subclasses to specify such dependencies.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    def inject_upstreams(self):
        self.add_upstream(another_task)
```


### `BaseRemoteCmdTask.insert_checker`

Inserts one or more `AnyTask` instances at the beginning of the current task's checker list.

This method is used to define dependencies for the current task. Tasks in the checker list are
executed before the current task. Adding a task to the beginning of the list means it will be
executed earlier than those already in the list.

__Arguments:__

- `checkers` (`TAnyTask`): One or more task instances to be added to the checker list.

__Examples:__

```python
from zrb import Task
task = Task(name='task')
checker_task = Task(name='checker-task')
task.insert_checker(checker_task)
```


### `BaseRemoteCmdTask.insert_env`

Inserts one or more `Env` instances at the beginning of the current task's environment variable list.

This method allows for setting or overriding environment variables for the task, with earlier entries
having precedence over later ones.

__Arguments:__

- `envs` (`Env`): One or more environment variable instances to be added.

__Examples:__

```python
from zrb import Task, Env
task = Task(name='task')
db_url_env = Env(name='DATABASE_URL', value='postgresql://...')
task.insert_env(env_var)
```


### `BaseRemoteCmdTask.insert_env_file`

Inserts one or more `EnvFile` instances at the beginning of the current task's environment file list.

This method is used to specify environment variable files whose contents should be loaded
before those of any files already in the list. This is useful for overriding or setting
additional environment configurations.

__Arguments:__

- `env_files` (`EnvFile`): One or more environment file instances to be added.

__Examples:__

```python
from zrb import Task, EnvFile
task = Task()
env_file = EnvFile(path='config.env')
task.insert_env_file(env_file)
```


### `BaseRemoteCmdTask.insert_input`

Inserts one or more `AnyInput` instances at the beginning of the current task's input list.

This method is used to add inputs that the task will process. Inserting an input at the beginning
of the list gives it precedence over those already present.

__Arguments:__

- `inputs` (`AnyInput`): One or more input instances to be added to the input list.

__Examples:__

```python
from zrb import Task, Input
task = Task(name='task')
email_input = Input(name='email-address')
task.insert_input(email_input)
```


### `BaseRemoteCmdTask.insert_upstream`

Inserts one or more `AnyTask` instances at the beginning of the current task's upstream list.

This method is used to define dependencies for the current task. Tasks in the upstream list are
executed before the current task. Adding a task to the beginning of the list means it will be
executed earlier than those already in the list.

__Arguments:__

- `upstreams` (`TAnyTask`): One or more task instances to be added to the upstream list.

__Examples:__

```python
from zrb import Task
task = Task(name='task')
upstream_task = Task(name='upstream-task')
task.insert_upstream(upstream_task)
```


### `BaseRemoteCmdTask.log_critical`

Log message with log level "CRITICAL"

You can set Zrb log level by using `ZRB_LOGGING_LEVEL` environment

### `BaseRemoteCmdTask.log_debug`

Log message with log level "DEBUG"

You can set Zrb log level by using `ZRB_LOGGING_LEVEL` environment

### `BaseRemoteCmdTask.log_error`

Log message with log level "ERROR"

You can set Zrb log level by using `ZRB_LOGGING_LEVEL` environment

### `BaseRemoteCmdTask.log_info`

Log message with log level "INFO"

You can set Zrb log level by using `ZRB_LOGGING_LEVEL` environment

### `BaseRemoteCmdTask.log_warn`

Log message with log level "WARNING"

You can set Zrb log level by using `ZRB_LOGGING_LEVEL` environment

### `BaseRemoteCmdTask.on_failed`

Specifies the behavior when the task execution fails.

This asynchronous method should be implemented in subclasses to handle task
failure scenarios. It can include logging the error, performing retries, or
any other failure handling mechanisms.

__Arguments:__

- `is_last_attempt` (`bool`): Indicates if this is the final retry attempt.
- `exception` (`Exception`): The exception that caused the task to fail.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def on_failed(self, is_last_attempt: bool, exception: Exception):
        if is_last_attempt:
            self.print_out('The task has failed with no remaining retries')
        else:
            self.print_out('The task failed, retrying...')
```


### `BaseRemoteCmdTask.on_ready`

Defines actions to be performed when the task status is `ready`.

This asynchronous method should be implemented in subclasses to specify
actions that occur when the task reaches the `ready` state. This can include
any cleanup, notification, or follow-up actions specific to the task.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def on_ready(self):
        self.print_out('The task is ready')
```


### `BaseRemoteCmdTask.on_retry`

Defines actions to perform when the task is retried.

Implement this method to specify behavior when the task is retried after a failure.
This could include resetting states, logging the retry attempt, or other necessary
steps before re-execution.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def on_retry(self):
        self.log_info('Retrying task')
```


### `BaseRemoteCmdTask.on_skipped`

Defines actions to perform when the task status is set to `skipped`.

Implement this method to specify behavior when the task is skipped. This could
include logging information, cleaning up resources, or any other necessary steps.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def on_skipped(self):
        self.log_info('Task was skipped')
```


### `BaseRemoteCmdTask.on_started`

Defines actions to perform when the task status is set to 'started'.

Implement this method to specify behavior when the task starts its execution. This
could involve initializing resources, logging, or other startup procedures.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def on_started(self):
        self.log_info('Task has started')
```


### `BaseRemoteCmdTask.on_triggered`

Defines actions to perform when the task status is set to `triggered`.

Implement this method to specify behavior when the task transitions to the
`triggered` state. This could involve setting up prerequisites or sending
notifications.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def on_triggered(self):
        self.log_info('Task has been triggered')
```


### `BaseRemoteCmdTask.on_waiting`

Defines actions to perform when the task status is set to `waiting`.

Implement this method to specify behavior when the task transitions to the
`waiting` state. This state usually indicates the task is waiting for some
condition or prerequisite to be met.

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def on_waiting(self):
        self.log_info('Task is waiting to be started')
```


### `BaseRemoteCmdTask.print_err`

Print message to stderr and style it as error.

### `BaseRemoteCmdTask.print_out`

Print message to stderr as normal text.

### `BaseRemoteCmdTask.print_out_dark`

Print message to stdout and style it as faint.

### `BaseRemoteCmdTask.print_result`

Print the task result to stdout for further processing.

Override this method in subclasses to customize how the task result is displayed
or processed. Useful for integrating the task output with other systems or
command-line tools.

__Arguments:__

- `result` (`Any`): The result of the task to be printed.

__Examples:__

```python
from zrb import Task
# Example of overriding in a subclass
class MyTask(Task):
   def print_result(self, result: Any):
       print(f'Result: {result}')
```


### `BaseRemoteCmdTask.render_any`

Render any value.

### `BaseRemoteCmdTask.render_bool`

Render int value.

### `BaseRemoteCmdTask.render_file`

Render file content.

### `BaseRemoteCmdTask.render_float`

Render float value.

### `BaseRemoteCmdTask.render_int`

No documentation available.


### `BaseRemoteCmdTask.render_str`

Render str value.

### `BaseRemoteCmdTask.run`

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

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def run(self, *args: Any, **kwargs: Any) -> int:
        self.print_out('Doing some calculation')
        return 42
```


### `BaseRemoteCmdTask.set_checking_interval`

Sets the interval for checking the task's readiness or completion status.

This method defines how frequently the system should check if the task is ready or completed.
It's useful for tasks that have an indeterminate completion time.

__Arguments:__

- `new_checking_interval` (`Union[float, int]`): The time interval (in seconds) for readiness or checks.

### `BaseRemoteCmdTask.set_color`

Defines a new color for the current task.

This method updates the color associated with the task. This can be useful for categorization,
priority indication, or visual differentiation in a UI.

__Arguments:__

- `new_color` (`str`): A string representing the color to be assigned to the task.

### `BaseRemoteCmdTask.set_description`

Sets a new description for the current task.

This method allows updating the task's description to provide more context or details about its purpose and behavior.
Useful for enhancing clarity and maintainability in the task management system.

__Arguments:__

- `new_description` (`str`): A string representing the new description of the task.

### `BaseRemoteCmdTask.set_icon`

Assigns a new icon to the current task.

This method is used for setting or updating the task's icon, which can be utilized for visual representation
in a user interface. The icon should ideally be a string identifier that maps to an actual graphical resource.

__Arguments:__

- `new_icon` (`str`): A string representing the icon identifier for the task.

### `BaseRemoteCmdTask.set_name`

Sets a new name for the current task.

This method is used to update the task's name, typically after creating a copy of an existing task.
The new name helps in differentiating the task in the task management system.

__Arguments:__

- `new_name` (`str`): A string representing the new name to be assigned to the task.

### `BaseRemoteCmdTask.set_retry`

Sets the number of retry attempts for the task.

This method configures how many times the task should be retried in case of failure.
It's essential for tasks that may fail transiently and need multiple attempts for successful execution.

__Arguments:__

- `new_retry` (`int`): An integer representing the number of retry attempts.

### `BaseRemoteCmdTask.set_retry_interval`

Specifies the interval between retry attempts for the task.

This method sets the duration to wait before retrying the task after a failure.
This can help in scenarios where immediate retry is not desirable or effective.

__Arguments:__

- `new_retry_interval` (`Union[float, int]`): The time interval (in seconds) to wait before a retry attempt.

### `BaseRemoteCmdTask.set_should_execute`

Determines whether the task should execute.

This method configures the execution criteria for the task. It can be set as a boolean value,
a string representing a condition, or a callable that returns a boolean. This is useful for
conditional task execution based on dynamic criteria.

__Arguments:__

- `should_execute` (`Union[bool, str, Callable[..., bool]]`): The condition to determine if the task should execute.

### `BaseRemoteCmdTask.set_task_xcom`

Set task xcom for cross task communication.

Argss:
key (str): Xcom key
value (str): The value of the xcom

__Returns:__

`str`: Empty string

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def run(self, *args: Any, **kwargs: Any) -> int:
        self.set_task_xcom('magic_word', 'hello')
        magic_word = self.get_xcom(f'{self.get_name()}.magic_word')
        return 42
```


### `BaseRemoteCmdTask.set_xcom`

Set xcom for cross task communication.

Argss:
key (str): Xcom key
value (str): The value of the xcom

__Returns:__

`str`: Empty string

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def run(self, *args: Any, **kwargs: Any) -> int:
        self.set_xcom('magic_word', 'hello')
        magic_word = self.get_xcom('magic_word')
        return 42
```


### `BaseRemoteCmdTask.to_function`

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

__Examples:__

```python
from zrb import Task
class MyTask(Task):
    async def run(self, *args: Any, **kwargs: Any) -> int:
        self.print_out('Doing some calculation')
        return 42
task = MyTask()
fn = task.to_function()
fn()
```


<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Task](./README.md)
