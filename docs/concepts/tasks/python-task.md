🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# `Task`

You can turn any function with `args` and `kwargs` argument into a Python Task.


```python
from zrb import Task, Env, StrInput, runner


def say_hello(*args, **kwargs) -> str:
    name = kwargs.get('name')
    greetings = f'Hello, {name}'
    return greetings


say_hello_task = Task(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='PYTHONUNBUFFERED', default=1)
    ],
    run=say_hello
)
runner.register(say_hello_task)
```

In the example, you define a function named `say_hello`.

Then you make a task named and set it's `run` property to `say_hello` function. As you notice, Zrb will automatically pass task input into `kwargs` argument.

You can run the task by invoking:

```
zrb say-hello --name John
```

Thiw will give you a `Hello John`.

# Using `python_task` decorator

Aside from defining the function and the task separately, you can also use `python_task` decorator to turn your function into a task.

```python
from zrb import python_task, Env, StrInput, runner

@python_task(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='PYTHONUNBUFFERED', default=1)
    ],
    runner=runner
)
def say_hello(*args, **kwargs) -> str:
    name = kwargs.get('name')
    greetings = f'Hello, {name}'
    task = kwargs.get('_task')
    task.print_out(greetings)
    return greetings
```

Notice that you can now use `runner` as decorator argument so that you don't need to call `runner.register(say_hello)`.

You can then run the task by invoking:

```bash
zrb say-hello --name=John
```

You can also use `async` function if you think you need to.

# `Task` parameters

When you create a Task, you need to provide some parameters. Some parameters are required, while some others are optionals.

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





🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
