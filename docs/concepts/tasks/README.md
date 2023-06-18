🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)


# Type of Tasks

There are many task types in Zrb. Every task has their own specific use-cases:


- [CmdTask](cmd-task.md): Run a CLI command
- [Task (python task)](python-task.md): Run a Python function
- [DockerComposeTask](docker-compose-task.md): Run a Docker compose Command
- [Resource Maker](resource-maker.md): Generate artifacts/resources based on templates
- [FlowTask](flow-task.md): Put `CmdTask` and `python task` into single flow.
- [Checkers (HttpChecker, PortChecker, and PathChecker)](checkers.md): Check parent task's readiness.

As every task are extended from `BaseTask`, you will see that most of them share some common parameters.


```
                              BaseTask
                                 │
                                 │
  ┌──────┬───────────┬───────────┼───────────┬───────────┬──────────┐
  │      │           │           │           │           │          │
  │      │           │           │           │           │          │
  ▼      ▼           ▼           ▼           ▼           ▼          ▼
Task  CmdTask  ResourceMaker  FlowTask  HttpChecker PortChecker PathChecker
         │
         │
         ▼
   DockerComposeTask
```

Aside from the documentation, you can always dive down into [the source code](https://github.com/state-alchemists/zrb/tree/main/src/zrb/task) to see the detail implementation.

> __Note:__ Never initiate `BaseTask` directly, use `Task` instead.

# Task overview

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
    retries=2,
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
zrb jupyterlab start 
```

As `start_jupyterlab` has `show_banner` as it's upstream, you can expect the `show_banner` to be executed prior to `start_jupyterlab`.

A task might also have multiple upstreams. In that case, the upstreams will be executed concurrently.

> __Note:__ Only tasks registered to `runner` are directly accessible from the CLI.

# Task Lifecycle

Every task has it's own lifecycle.

```
   ┌────────────────────────────┐
   │                            │
   │                            ▼
   │                     ┌──► Ready ────► Stopped
   │                     │                   ▲
Waiting ────► Started ───┤                   │
                 ▲       │                   │
                 │       └──► Failed ────────┘
                 │              │
                 │              │
                 │              ▼
                 └─────────── Retry
```

- `Waiting`: Task won't be started until all it's upstreams are ready.
- `Started`: Zrb has start the task.
- `Failed`: The task is failed, due to internal error or other causes. A failed task can be retried or stopped, depends on `retries` setting.
- `Retry`: The task has been failed and now rescheduled to be started.
- `Ready`: The task is ready. Some tasks are automatically stopped after ready, but some others keep running in the background (e.g., web server, scheduler, etc)
- `Stopped`: The task is no longer running.

# Task parameters

Every task has different parameters, please refer to each [task-specific](#type-of-tasks) documentation for further information.

# Task methods

All tasks share some common methods.

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

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md)
