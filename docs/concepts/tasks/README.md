🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)

# Task

Tasks are the building block of automation. In general, all tasks are extended from `BaseTask`.

```
                               BaseTask
  ┌------┬---------┬--------------┼------------┬------------┐					
  |      |         |              |            |            |
Task  CmdTask ResourceMaker  HttpChecker  PathChecker  PortChecker
         |
DockerComposeTask
```

All tasks share some common properties and methods.

Let's see the following task declaration:

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
    retries=2,
    retry_interval=3
)

# registering `show_banner` to zrb runner
runner.register(start_jupyterlab)
```

You can try to run `start_jupyterlab` task as follow:

```bash
export EMPLOYEE="Yorinobu Arasaka"
zrb jupyterlab start
```

The command will:
- Show you an Arasaka banner
- Welcome Yorinobu Arasaka
- Start Jupyterlab on the port you choose (by default it is `8080`)

Task might have multiple upstreams. Task upstreams will be executed concurrently.

# Task Lifecycle

Task has it's own lifecycle.

```
   ┏-----------------------------┐
   |                             v
   |                     ┏---> Ready ---> Stopped
Waiting ----> Started ---┫                  ^	
                ^        ┗---> Failed ------┛
                |                |
                └----------------┛
```

- `Waiting`: Task won't be started until all it's upstreams are ready.
- `Started`: Zrb has start the task.
- `Failed`: The task is failed, due to internal error or other causes. A failed task can be retried or stopped, depends on `retries` setting.
- `Ready`: The task is ready. Some tasks are automatically stopped after ready, but some others keep running in the background (e.g., web server, scheduler, etc)
- `Stopped`: The task is no longer running.

# Task parameters

In common, every Zrb tasks has some properties.

## `name`

Name of the task. Once a task is registered to Zrb runner, you will be able to execute a task by it's name (i.e., `zrb [groups] <task-name>`)

- __Required:__ True
- __Possible values:__ Any string

## `icon`

Icon representing the task. If not set, Zrb will choose a random icon for your task.

- __Required:__ False
- __Possible values:__ Any emoji
- __Default value:__ Set randomly during runtime:
    - 🐶
    - 🐱
    - 🐭
    - 🐹
    - 🦊
    - 🐻
    - 🐨
    - 🐯
    - 🦁
    - 🐮
    - 🐷
    - 🍎
    - 🍐,
    - etc...


## `color`

Color representing the task. If not set, Zrb will choose a random color for your task.

- __Required:__ False
- __Possible values:__ Any valid color
- __Default value:__ Set randomly during runtime:
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

## `checkers`

List of checker tasks to mark task as ready.

A lot of background processes will keep running forever. You need a way to make sure whether the process is ready or not.

To do this, we can use another type of tasks:

- `PortChecker`: Check whether TCP port is ready or not.
- `PathChecker`: Check whether file/directory is exists.
- `HttpChecker`: Check whether HTTP port is ready or not.

Let's see some example:

```python
from zrb import CmdTask, HttpChecker, PathChecker, runner

build_frontend = CmdTask(
    name='build-frontend',
    cmd='npm run build --watch',
    checkers=[
        PathChecker(path='src/frontend/build')
    ]
)
runner.register(build_frontend)

start_server = CmdTask(
    name='start-server',
    cmd='nodemon start',
    upstreams=[build_frontend],
    checkers=[
        HttpChecker(port='80', url='/readiness')
    ]
)
runner.register(start_server)
```

The `build_frontend` task will keep running in the background. It will check for any changes, and re-compile the frontend.
You can consider `build_frontend` to be ready if `src/frontend/build` is exists.

Once `build_frontend` ready, `start_server` can be started. This task is considered as ready once port 80 is available.

- __Required:__ False
- __Possible values:__ List of `Task` object
- __Default value:__ `[]`

## `retry`

How many time the task will be retried before it is considered as fail.

- __Required:__ False
- __Possible values:__ Integer numbers, greater or equal to `0`
- __Default value:__ `2`

## `retry_interval`

Inter retry interval.

- __Required:__ False
- __Possible values:__ Any number greater or equal to `0`
- __Default value:__ `0`

## `skip_execution`

Boolean, a function returning a boolean, or Jinja syntax that rendered to boolean.

If `skip_execution` is evaluated to `True`, then the task will be considered as completed without being started.

- __Required:__ False
- __Possible values:__ Boolean, a function returning a boolean, or Jinja syntax that rendered to boolean.
- __Default value:__ `False`


# Task methods

## `run`

Method to be executed when a task is tarted. You can extend BaseTask and override this method if you think you need to.

Example:

```python
class MyTask(BaseTask):

    def run(self, *args: Any, **kwargs: Any) -> Any:
        task = kwargs.get('_task') 
        task.print_out(f'args: {args}, kwargs: {kwargs}')
        return super().run(*args, **kwargs)
```

## `check`

Method to check task readiness. You can extend BaseTask and override this method if you think you need to.

Example:

```python
class MyTask(BaseTask):

    def check(self) -> bool:
        return super().check()
```

## `create_main_loop`

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

show_banner_loop = show_banner.create_main_loop()
print(show_banner_loop())
```

# Type of Tasks

There are many task types in Zrb:

- [CmdTask](cmd-task.md)
- [Task (pythonTask)](python-task.md)
- [DockerComposeTask](docker-compose-task.md)
- [Checkers](checkers.md)

You can always dive down into [the source code](https://github.com/state-alchemists/zrb/tree/main/src/zrb/task) to see the detail implementation, but make sure you have read the documentation first.

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)
