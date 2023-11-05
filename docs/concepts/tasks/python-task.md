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
        Env(name='PYTHONUNBUFFERED', default='1')
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
        Env(name='PYTHONUNBUFFERED', default='1')
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

# Task Parameters

Every [common task parameters](./README.md#common-task-parameters) are applicable here. Additionally, a `Task` has some specific parameters.

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

# python_task parameters

When you create a python task using `python_task` decorator, you can use all parameters defined in [the previous section](#task-parameters).

Furthermore, you can also define `runner` parameter.

## `runner`

Runner this task registered to.

- __Required:__ False
- __Possible values:__ `runner` or `None`
- __Default value:__ `runner`

# Task Methods

Please refer to [common task methods](./README.md#common-task-methods).


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
