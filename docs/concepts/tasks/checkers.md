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

For internal use

### `Checker._mark_awaited`

No documentation available.


### `Checker._mark_done`

No documentation available.


### `Checker._play_bell`

No documentation available.


### `Checker._print_result`

For internal use

### `Checker._propagate_execution_id`

No documentation available.


### `Checker._run_all`

For internal use

### `Checker._run_and_check_all`

No documentation available.


### `Checker._set_args`

No documentation available.


### `Checker._set_env_map`

No documentation available.


### `Checker._set_execution_id`

Sets the execution ID for the current task.

This method is intended for internal use to assign a unique identifier to the task's execution.
This ID can be used for tracking, logging, and inter-task communication.

This method should not be used externally, as it is meant to be managed within the task system.

__Arguments:__

- `execution_id` (`str`): A string representing the unique execution ID.

### `Checker._set_has_cli_interface`

No documentation available.


### `Checker._set_input_map`

No documentation available.


### `Checker._set_keyval`

For internal use

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


### `Checker.add_env_file`

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


### `Checker.add_input`

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


### `Checker.add_upstream`

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


### `Checker.check`

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


### `Checker.copy`

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


### `Checker.insert_env_file`

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


### `Checker.insert_input`

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


### `Checker.insert_upstream`

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


### `Checker.on_ready`

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


### `Checker.on_retry`

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


### `Checker.on_skipped`

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


### `Checker.on_started`

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


### `Checker.on_triggered`

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


### `Checker.on_waiting`

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


### `Checker.print_err`

No documentation available.


### `Checker.print_out`

No documentation available.


### `Checker.print_out_dark`

No documentation available.


### `Checker.print_result`

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