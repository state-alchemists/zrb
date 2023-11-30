🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)


# Type of Tasks

There are many task types in Zrb. Every task has its own specific use cases:


- [CmdTask](cmd-task.md): Run a CLI command
- [Task (python task)](python-task.md): Run a Python function
- [DockerComposeTask](docker-compose-task.md): Run a Docker compose Command
- [ResourceMaker](resource-maker.md): Generate artifacts/resources based on templates
- [FlowTask](flow-task.md): Put `CmdTask` and `python task` into single flow.
- [RemoteCmdTask](remote-cmd-task.md)
- [RsyncTask](rsync-task.md)
- [Checkers (HttpChecker, PortChecker, and PathChecker)](checkers.md): Check parent task's readiness.

As every task are extended from `BaseTask`, you will see that most of them share some common parameters.


```
                                           BaseTask
                                               │
                                               │
  ┌──────┬───────────┬───────────┬─────────────┼─────────────────┬─────────────┬───────────┬──────────┐
  │      │           │           │             │                 │             │           │          │
  │      │           │           │             │                 │             │           │          │
  ▼      ▼           ▼           ▼             ▼                 ▼             ▼           ▼          ▼
Task  CmdTask  ResourceMaker  FlowTask  BaseRemoteCmdTask  ReccuringTask  HttpChecker PortChecker PathChecker
         │                                     │
         │                                     │
         ▼                               ┌─────┴──────┐
   DockerComposeTask                     │            │
                                         ▼            ▼
                                   RemoteCmdTask   RsyncTask
```

Aside from the documentation, you can always dive down into [the source code](https://github.com/state-alchemists/zrb/tree/main/src/zrb/task) to see the detail implementation.

> __📝 NOTE:__ Never initiate `BaseTask` directly, use `Task` instead.

# Task Overview

Tasks are building blocks of your automation.

Let's see how you can define tasks and connect them to each others:

```python
from zrb import CmdTask, IntInput, Env, Group, runner, PortChecker

# defining two groups: arasaka, and jupyterlab
# jupyterlab is located under arasaka
arasaka = Group(name='arasaka', description='Arasaka automation')
jupyterlab = Group(name='jupyterlab', parent=arasaka, description='Jupyterlab related tasks')

# defining show banner under `arasaka` group
show_banner = CmdTask(
    name='show-banner',
    icon='🎉',
    color='yellow',
    description='Show banner',
    group=arasaka,
    envs=[
        # EMPLOYEE enviornment variable will be accessible from inside the task as USER.
        # The default value this variable will be `employee`.
        Env(name='USER', os_name='EMPLOYEE', default='employee')
    ],
    cmd=[
        'figlet Arasaka',
        'echo "Welcome $USER"'
    ]
)

# registering `show_banner` to zrb runner
runner.register(show_banner)

# defining show banner under `arasaka jupyterlab` group
start_jupyterlab = CmdTask(
    name='start',
    icon='🧪',
    color='green',
    description='Start Jupyterlab',
    group=jupyterlab,
    inputs=[
        # Port where jupyterlab should be started
        IntInput(name='jupyterlab-port', default=8080)
    ],
    # start_jupyterlab depends on show_banner
    upstreams=[show_banner],
    cmd='jupyter lab --no-browser --port={{input.jupyterlab_port}}',
    checkers=[
        PortChecker(port='{{input.jupyterlab_port}}')
    ],
    retry=2,
    retry_interval=3
)

# registering `show_banner` to zrb runner
runner.register(start_jupyterlab)
```


You can try to run `start_jupyterlab` task as follow:

```bash
export EMPLOYEE="Yorinobu Arasaka"

# The following command will
# - Show Arasaka Banner
# - Start jupyterlab on the port you choose (by default it is 8080)
zrb arasaka jupyterlab start 
```

As `start_jupyterlab` has `show_banner` as it's upstream, you can expect the `show_banner` to be executed prior to `start_jupyterlab`.

A task might also have multiple upstreams. In that case, the upstreams will be executed concurrently.

> __📝 NOTE:__ Only tasks registered to `runner` are directly accessible from the CLI.

# Task Lifecycle

Every task has it's own lifecycle.

```
Triggered         ┌─────────► Ready ◄──┐
    │             │                    │
    │             │                    │
    ▼             │                    │
 Waiting ────► Started ─────► Failed   │
    │             ▲             │      │
    │             │             │      │
    ▼             │             ▼      │
 Skipped          └────────── Retry    │
    │                                  │
    │                                  │
    └──────────────────────────────────┘
```

- `Triggered`: Task is triggered.
- `Waiting`: Task is waiting all upstreams to be ready.
- `Skipped`: Task is not executed and will enter ready state soon.
- `Started`: Task has been started.
- `Failed`: Task is failed, will enter `Retry` state if retries is less than max attempt.
- `Retry`: The task has been failed and will be re-started.
- `Ready`: The task is ready.

# Common Task Parameters

Zrb tasks share some common parameters like `name`, `icon`, `color`, `description`, etc.

Some parameters are required, while some others are optional. Please refer to [each specific task documentation](#type-of-tasks) for a more complete list of parameters.

## `name`

Task name

- __Required:__ True
- __Possible values:__ Any string

## `color`

Color representing the task. If not set, Zrb will choose a random color for your task.

- __Required:__ False
- __Possible values:__ 
    - `green`
    - `yellow`
    - `blue`
    - `magenta`
    - `cyan`
    - `light_green`
    - `light_yellow`
    - `light_blue`
    - `light_magenta`
    - `light_cyan`
- __Default value:__ One of the possible values, set randomly during runtime.
    
## `icon`

Icon representing the task. If not set, Zrb will choose a random icon for your task.

- __Required:__ False
- __Possible values:__ Any emoji
- __Default value:__ Set randomly during runtime

## `description`

Description of the task.

- __Required:__ False
- __Possible values:__ Any string
- __Default value:__ Empty string

## `group`

Task group where the current task is located.

You can create a group like this:

```python
arasaka = Group(name='arasaka', description='Arasaka automation')
```

You can also put a group under another group:

```python
jupyterlab = Group(name='jupyterlab', parent=arasaka, description='Jupyterlab related tasks')
```

- __Required:__ False
- __Possible values:__ `Group` or `None`
- __Default value:__ `None`

## `inputs`

List of task inputs. There are multiple type of task inputs you can choose:

- `BoolInput`
- `ChoiceInput`
- `FloatInput`
- `IntInput`
- `PasswordInput`
- `StrInput`

See the following example:

```python
from zrb import (
    runner, CmdTask,
    StrInput, ChoiceInput, IntInput, BoolInput, FloatInput, PasswordInput
)

register_trainer = CmdTask(
    name='register-trainer',
    inputs=[
        StrInput(name='name', default=''),
        PasswordInput(name='password', default=''),
        IntInput(name='age', default=0),
        BoolInput(name='employed', default=False),
        FloatInput(name='salary', default=0.0),
        ChoiceInput(
            name='starter-pokemon',
            choices=['bulbasaur', 'charmender', 'squirtle']
        )
    ],
    cmd=[
        'echo "Name: {{input.name}}"',
        'echo "Password (sorry, we should not show this): {{input.password}}"',
        'echo "Age: {{input.age}}"',
        'echo "Employed: {{input.employed}}"',
        'echo "Salary: {{input.salary}}"',
        'echo "Starter Pokemon: {{input.starter_pokemon}}"',
    ]
)
runner.register(register_trainer)
```

> Note: When you access inputs using Jinja (i.e., `{{input.snake_input_name}}`) syntax, input name is automatically snake-cased.


- __Required:__ False
- __Possible values:__ List of `Input` object
- __Default value:__ `[]`


## `envs`

List of task envs. Task envs allow you to map task environment into os environment.

In the following example, we map OS `$EMPLOYEE` into task `$USER`, as well as set default value `employee` to the task env variable:

```python
from zrb import CmdTask, Env, runner

show_banner = CmdTask(
    name='show-banner',
    envs=[
        Env(name='USER', os_name='EMPLOYEE', default='employee')
    ],
    cmd=[
        'figlet Arasaka',
        'echo "Welcome $USER"'
        'echo "こんにちは {{env.USER}}"'
    ]
)
runner.register(show_banner)
```

Just like `input`, you can also use Jinja syntax (i.e., `{{env.USER}}`)

- __Required:__ False
- __Possible values:__ List of `Env` object
- __Default value:__ `[]`

## `env_files`

List of task environment files.

Defining environment can be a challenging task, especially if you have a lot of it. Zrb allows you load environment from `*.env` file.

For example, you have the following environment file:

```bash
# File location: template.env
PORT=8080
INSTALL_REQUIREMENTS=1
```

You can load the environment file like the following:

```python
from zrb import CmdTask, EnvFile, runner

# defining show banner under `arasaka jupyterlab` group
start_jupyterlab = CmdTask(
    name='start-jupyter',
    env_files=[
        EnvFile(env_file='/path/to/template.env', prefix='JUPYTER')
    ],
    cmd=[
        'if [ "$INSTALL_REQUIREMENTS" = "1" ]',
        'then',
        '    pip install -r requirements.txt',
        'fi',
        'jupyter lab --no-browser --port={{env.PORT}}',
    ],
    checkers=[
        PortChecker(port='{{env.PORT}}')
    ]
)

# registering `show_banner` to zrb runner
runner.register(start_jupyterlab)
```

Finally, you can set `PORT` and `INSTALL_REQUIREMENTS` using your environment file prefix (`JUPYTER`):

```bash
export JUPYTER_PORT=3000
export INSTALL_REQUIREMENTS=0
zrb start-jupyter
```

This will let you avoid environment variable colisions.

- __Required:__ False
- __Possible values:__ List of `EnvFile` object
- __Default value:__ `[]`

## `upstreams`

List of upstream tasks. Before running a task, Zrb will make sure that it's upstreams are ready.

Just like in our previous example `start_jupyterlab` will not started before `show_banner` is ready.

- __Required:__ False
- __Possible values:__ List of `Task` object
- __Default value:__ `[]`

## `should_execute`

Boolean, a function returning a boolean, or Jinja syntax that rendered to boolean.

If `should_execute` is evaluated to `True`, then the task will be executed.

- __Required:__ False
- __Possible values:__ Boolean, a function returning a boolean, or Jinja syntax that rendered to boolean.
- __Default value:__ `True`


## `return_upstream_result`

Boolean, whether return upstreams result instead of current task result or not.

- __Required:__ False
- __Possible values:__ Boolean, a function returning a boolean, or Jinja syntax that rendered to boolean.
- __Default value:__ `False`

## `on_triggered`

## `on_waiting`

## `on_skipped`

## `on_started`

## `on_ready`

## `on_retry`

## `on_failed`


# Common Task Methods

Every task share some common methods like `run`, `check`, and `to_function`.

## `copy`

Deep copy current task

## `inject_env`

To be overridden

## `insert_env`

## `add_env`

## `inject_env_file`

To be overridden

## `insert_env_file`

## `add_env_file`

## `inject_input`

To be overridden

## `insert_input`

## `add_input`

## `inject_upstream`

To be overridden

## `insert_upstream`

## `add_upstream`

## `inject_checker`

To be overridden

## `insert_checker`

## `add_checker`

## `set_name`

## `set_description`

## `set_icon`

## `set_color`

## `set_should_execute`

## `set_retry`

## `set_retry_interval`

## `set_checking_interval`

## `get_env_map`

Return task environments as dictionary.

This is typically useful if you create a Python task. Zrb won't override `os.environ`, so you can't load task environment using `os.environ.get` or `os.getenv`. Instead, you have to use `task.get_env_map`.

Example:

```python
from zrb import Task, Env, python_task, runner

@python_task(
    name='show-env',
    envs=[
        Env(name='POKEMON_NAME', default='charmender'),
        Env(name='ELEMENT', default='fire'),
    ],
    runner=runner
)
def show_env(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    inputs = task.get_env_map()
    return inputs # should return {'POKEMON_NAME': 'charmender', 'ELEMENT': 'fire'}
```

## `get_input_map`

Return task inputs as dictionary.

This is typically useful if you create a Python task.

Example:

```python
from zrb import Task, StrInput, python_task, runner

@python_task(
    name='show-env',
    inputs=[
        StrInput(name='pokemon-name', default='charmender'),
        StrInput(name='element', default='fire'),
    ],
    runner=runner
)
def show_env(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    inputs = task.get_input_map()
    return inputs # should return {'pokemon_name': 'charmender', 'element': 'fire'}
```

## `run`

Method to be executed when a task is started. You can extend `BaseTask` and override this method if you think you need to.

Example:

```python
from zrb import BaseTask, Task

class MyTask(BaseTask):

    def run(self, *args: Any, **kwargs: Any) -> Any:
        task: Task = kwargs.get('_task') 
        task.print_out(f'args: {args}, kwargs: {kwargs}')
        # TODO: do anything here
        return super().run(*args, **kwargs)
```

## `check`

Method to check task readiness. You can extend `BaseTask` and override this method if you think you need to.

Example:

```python
from zrb import BaseTask

class MyTask(BaseTask):

    def check(self) -> bool:
        # TODO: Add your custom checking here
        return super().check()
```

## `on_triggered`

## `on_waiting`

## `on_skipped`

## `on_started`

## `on_ready`

## `on_retry`

## `on_failed`

## `to_function`

Method to create main-loop. Once a main-loop is created, you can perform a function call to it.

Example:

```python
from zrb import CmdTask, Env, runner

show_banner = CmdTask(
    name='show-banner',
    envs=[
        Env(name='USER', os_name='EMPLOYEE', default='employee')
    ],
    cmd=[
        'figlet Arasaka',
        'echo "Welcome $USER"'
        'echo "こんにちは {{env.USER}}"'
    ]
)

show_banner_loop = show_banner.to_function()
print(show_banner_loop()) # Now you can run your task as a normal python function
```

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)
