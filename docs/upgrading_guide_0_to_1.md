🔖 [Documentation Home](../README.md) > Upgrading Guide

# Upgrading Guide from 0.x.x to 1.x.x

Zrb 1.x.x introduced significant changes and improvements over the 0.x.x series. This guide will help you migrate your existing Zrb task definitions from the old structure to the new one.

The core concepts of Tasks, Groups, and dependencies remain, but their definition and registration methods have been streamlined and unified under the `cli` object.

Here's a breakdown of the key changes:

## Session and Context

Zrb 1.x.x introduces the concepts of `Session` and `Context`. Each task run operates within its own `Session`, providing isolation. The `Context` object, passed to task actions, contains session-specific information, including environment variables, inputs, and access to utilities like `ctx.print`. This isolation ensures that concurrent task runs do not interfere with each other.

## Simple Example

Here's a quick look at how a basic task definition and registration differs between 0.x.x and 1.x.x:

**0.x.x:**
```python
from zrb import Task, runner

# Define a simple task
hello_task = Task(
    name='hello',
    run=lambda ctx: print("Hello from 0.x.x!")
)

# Register the task
runner.register(hello_task)
```

**1.x.x:**
```python
from zrb import Task, cli

# Define a simple task and register it with cli
hello_task = cli.add_task(
    Task(
        name='hello',
        action=lambda ctx: print("Hello from 1.x.x!") # 'run' is now 'action'
    )
)
```

As you can see, the main changes involve importing `cli` instead of `runner` and using `cli.add_task()` directly during task definition. Also, the `run` parameter in the `Task` constructor is renamed to `action`.

## 1. `runner` is replaced by `cli`

In 0.x.x, you registered tasks using `runner.register()`. In 1.x.x, task and group registration is handled by the `cli` object.

**0.x.x:**
```python
from zrb import Task, runner

my_task = Task(...)
runner.register(my_task)
```

**1.x.x:**
```python
from zrb import Task, cli

my_task = Task(...)
cli.add_task(my_task)
```

## 2. Group Definition and Registration

Groups are now also registered via the `cli` object or their parent group. The `parent` parameter in the `Group` constructor is no longer used for registration.

**0.x.x:**
```python
from zrb import Group, Task, runner

parent_group = Group('parent')
child_group = Group('child', parent=parent_group)
my_task = Task(group=child_group, ...)

runner.register(parent_group) # Registering the parent group makes children accessible
```

**1.x.x:**
```python
from zrb import Group, Task, cli

# Define and register the parent group with cli
parent_group = cli.add_group(Group('parent'))

# Define the child group and add it to the parent
child_group = parent_group.add_group(Group('child'))

# Define the task and add it to the child group
my_task = child_group.add_task(Task(...))
```

## 3. Task Definition (`Task` class)

The basic `Task` class structure is similar, but registration is different as mentioned above.

**0.x.x:**
```python
from zrb import Task, runner, Env

my_task = Task(
    name='my-task',
    envs=[Env(name='MY_VAR', default='default')],
    upstreams=[other_task],
    should_execute='{{env.MY_VAR == "value"}}',
    run=lambda ctx: print(f"My var is {ctx.env.MY_VAR}"),
    description='My task description'
)
runner.register(my_task)
```

**1.x.x:**
```python
from zrb import Task, cli, Env

my_task = Task(
    name='my-task',
    env=[Env(name='MY_VAR', default='default')], # 'envs' is now 'env' and can be a single Env, EnvMap, EnvFile, or list
    upstream=[other_task], # 'upstreams' is now 'upstream' and can be a single Task or list
    execute_condition='{{ctx.env.MY_VAR == "value"}}', # 'should_execute' is now 'execute_condition'
    action=lambda ctx: print(f"My var is {ctx.env.MY_VAR}"), # 'run' is now 'action'
    description='My task description'
)
cli.add_task(my_task)
```
Note the parameter name changes: `envs` to `env`, `upstreams` to `upstream`, `should_execute` to `execute_condition`, and `run` to `action`.

## 4. `@python_task` decorator is now `@make_task`

The `@python_task` decorator has been renamed to `@make_task` and is used to turn a Python function into a Zrb Task. You can register the task directly with a group (like `cli`) using the `group` parameter in the decorator.

**0.x.x:**
```python
from zrb import python_task, runner

@python_task(name='my-decorated-task')
def my_decorated_task(*args, **kwargs):
    print("This is a decorated task")

runner.register(my_decorated_task)
```

**1.x.x:**
```python
from zrb import make_task, cli

@make_task(name='my-decorated-task', group=cli) # Register directly with cli
def my_decorated_task(ctx):
    print("This is a decorated task")
```

### Printing Output

In 0.x.x, you would typically use `task.print_out` to print output within a `@python_task`. In 1.x.x, you should use `ctx.print`.

**0.x.x:**
```python
from zrb import python_task, runner, Task
from typing import Any

@python_task(
    name='deploy',
    # ... other parameters
)
def deploy(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Ok')
```

**1.x.x:**
```python
from zrb import make_task, cli
from zrb.context import Context
from typing import Any

@make_task(
    name='deploy',
    group=cli, # Assuming it's registered with cli
    # ... other parameters
)
def deploy(ctx: Context, *args: Any, **kwargs: Any):
    ctx.print('Ok')
```

## 5. `Env` Definition

The `Env` class is still used, but the parameter name for linking to the OS environment variable has changed from `link_to_os` to `link_to_os`. Also, you can now use `EnvMap` or `EnvFile` for defining multiple environment variables or loading from a `.env` file.

**0.x.x:**
```python
from zrb import Env

my_env = Env(name='MY_VAR', default='default', link_to_os=True)
```

**1.x.x:**
```python
from zrb import Env

my_env = Env(name='MY_VAR', default='default', link_to_os=True) # 'link_to_os' is now 'link_to_os'
```

## 6. Upstream Dependencies

The concept of upstream dependencies remains the same, but the parameter name in the `Task` constructor is now `upstream` (singular) instead of `upstreams` (plural). The `>>` operator is still available for defining dependencies.

**0.x.x:**
```python
from zrb import Task, runner

task1 = Task(name='task1', ...)
task2 = Task(name='task2', upstreams=[task1], ...)

runner.register(task1)
runner.register(task2)
```

**1.x.x:**
```python
from zrb import Task, cli

task1 = Task(name='task1', ...)
task2 = Task(name='task2', upstream=[task1], ...) # 'upstreams' is now 'upstream'

cli.add_task(task1)
cli.add_task(task2)

# Alternatively, using the >> operator:
# task1 >> task2
# cli.add_task(task1)
# cli.add_task(task2)
```

## 7. CmdPath is now a class

**0.x.x:**
```python
from zrb import CmdTask

task = CmdTask(cmd_path=os.path.join("dir", "command.sh"))
```

**1.x.x:**
```python
from zrb import CmdTask, CmdPath

task = CmdTask(cmd=CmdPath(os.path.join("dir", "command.sh")))
```

## Available Task Types

Zrb 1.x.x provides several built-in task types to handle various operations:

*   [`CmdTask`](./task/types/cmd_task.md): For executing shell commands.
*   [`HttpCheck`](./task/types/http_check.md): For performing HTTP health checks.
*   [`LlmTask`](./task/types/llm_task.md): For integrating with Language Model APIs.
*   [`RsyncTask`](./task/types/rsync_task.md): For synchronizing files and directories using rsync.
*   [`Scaffolder`](./task/types/scaffolder.md): For generating files from templates.
*   [`Task`](./task/types/task.md): The base class for creating custom Python tasks (used with `@make_task`).
*   [`TcpCheck`](./task/types/tcp_check.md): For performing TCP port health checks.

### Migrating from DockerComposeTask

The `DockerComposeTask` from 0.x.x has been removed in 1.x.x. You can achieve the same functionality by using the `CmdTask` to execute `docker compose` commands.

**0.x.x:**
```python
from zrb import DockerComposeTask, runner

# Assuming a docker-compose.yml file exists
docker_up_task = DockerComposeTask(
    name='docker-up',
    command='up'
)

runner.register(docker_up_task)
```

**1.x.x:**
```python
from zrb import CmdTask, cli

# Assuming a docker-compose.yml file exists
docker_up_task = cli.add_task(
    CmdTask(
        name='docker-up',
        cmd='docker compose up -d'
    )
)
```

🔖 [Documentation Home](../README.md)