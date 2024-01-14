🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Runner, Group, and Task

Runner, task, and group are some pretty simple but important concepts in Zrb. Let's see how they are related to each other.

# Runner

<div align="center">
  <img src="../_images/emoji/runner.png"/>
  <p>
    <sub>
      <a href="https://www.youtube.com/watch?v=2wVPyo_hnWw" target="_blank">Run! run! run!</a>
    </sub>
  </p>
</div>

To make a Zrb Task accessible from the CLI, you need to register the Task to the Runner. You can import Zrb Runner as follows:

```python
from zrb import runner
```

## Registering Tasks to Runner

Once you import a Zrb Runner, you can use it to register your task as follows:

```python
from zrb import runner, Task

task = Task(name='task')
runner.register(task)
```

To access the registered Task, you need to run the following command in your terminal:

```bash
zrb task
```

## Registering Grouped Tasks to Runner

You can also put your Task under Task Groups.

```python
from zrb import runner, Task, Group

group = Group(name='group)
task = Task(name='task', group=group)
runner.register(task)
```

To access the registered Grouped Task, you can run the following command in your terminal:

```bash
zrb group task
```

## Limitations And Restrictions

- You can only register a Task once.
- Registered Tasks cannot have the same names under the same Group names.

Let's see some examples:

### Invalid Examples

The following example is invalid because you can only register a Task once:

```python
from zrb import runner, Task

task = Task(name='task')
runner.register(task)
runner.register(task) # This yield error.
```

The following is invalid because the Tasks shared the same name:

```python
from zrb import runner, Task

task_1 = Task(name='task')
runner.register(task_1)

task_2 = Task(name='task')
runner.register(task_2) # This yield error.
```

The following is also invalid because the Tasks shared the same name and were under the same Group name.

```python
from zrb import runner, Group, Task

group = Group(name='group')

task_1 = Task(name='task', group=group)
runner.register(task_1)

task_2 = Task(name='task', group=Group(name='group'))
runner.register(task_2) # This yield error.
```

### Valid Examples

The following example is valid. Even though `task_1` and `task_2` shared the same name, they were defined under different Groups.

```python
from zrb import runner, Task, Group

task_1 = Task(name='task')
runner.register(task_1)

task_2 = Task(name='task', group=Group(name='group'))
runner.register(task_2) # OK, task_1 and task_2 are located under different group
```

# Group

<div align="center">
  <img src="../_images/emoji/file_cabinet.png"/>
  <p>
    <sub>
      Put related Tasks under the same Group for better discoverability.
    </sub>
  </p>
</div>

You can use Group to organize your Tasks. A Group will only be accessible from the CLI if at least one registered Task is located under the Group.

You can also put a Group under another Group.

Hierarchically speaking, you can think of Task Groups as directories to organize your Tasks.The following are some built-in Tasks and Task Groups in Zrb.

```
zrb
├── base64
│   ├── decode
│   └── encode
├── devtool
│   ├── install
│   │   ├── aws
│   │   ├── docker
│   │   ├── gcloud
│   │   ├── ...
│   │   └── zsh
├── explain
│   ├── dry-principle
│   ├── kiss-principle
│   ├── solid-principle
│   ├── ...
│   └── zen-of-python
├── ...
└── watch-changes
```

Let's see how you can organize your Tasks under hierarchical Groups:

```python
from zrb import runner, Task, Group

util = Group(name='util')
base64 = Group(name='json', parent=util)

encode = Task(name='encode', group=base64)
runner.register(encode)

decode = Task(name='decode', group=base64)
runner.register(decode)
```

In the example, you have a `json` Task Group under `util` Task Group. The `json` Task Group contains two Tasks: `encode` and `decode`.

To access both `encode` and `decode`, you can use the following command from the CLI:

```bash
zrb util json encode
zrb util json decode
```

By using Task Group, you can make your Tasks more organized.

# Task

<div align="center">
  <img src="../_images/emoji/clipboard.png"/>
  <p>
    <sub>
      Finishing a task: 10% skill, 90% not getting distracted by the internet.
    </sub>
  </p>
</div>

Tasks are the most basic unit in Zrb. There are many Task Classes you can use to create a Task.

- [Task](../technical-documentation/tasks/task.md): General purpose class, usually created using [@python_task](../technical-documentation/tasks/python-task.md) decorator.
- [CmdTask](../technical-documentation/tasks/cmd-task.md): Run a CLI command/shell script.
- [DockerComposeTask](../technical-documentation/tasks/docker-compose-task.md): Run any docker-compose related command (e.g., `docker compose up`, `docker compose down`, etc.)
- [RemoteCmdTask](../technical-documentation/tasks/remote-cmd-task.md): Run a CLI command/shell script on remote computers using SSH.
- [RsyncTask](../technical-documentation/tasks/rsync-task.md): Copy file from/to remote computers using `rsync` command.
- [ResourceMaker](../technical-documentation/tasks/resource-maker.md): Create resources (source code/documents) based on provided templates.
- [FlowTask](../technical-documentation/): Combine unrelated tasks into a single Workflow.
- [RecurringTask](../technical-documentation/tasks/recurring-task.md): Create a long-running recurring task.

You can see the relation among Zrb Task Classes in the following diagram: 

```
                                            AnyTask
                                               │
                                               │
                                               ▼
                                           BaseTask
                                               │
                                               │
  ┌──────┬───────────┬───────────┬─────────────┼─────────────────┬────────────┐
  │      │           │           │             │                 │            │
  │      │           │           │             │                 │            │
  ▼      ▼           ▼           ▼             ▼                 ▼            ▼
Task  CmdTask  ResourceMaker  FlowTask  BaseRemoteCmdTask     Checker   ReccuringTask
         │                                     │                 │
         │                                     │                 │
         ▼                               ┌─────┴──────┐          │
   DockerComposeTask                     │            │          │
                                         ▼            ▼          │
                                   RemoteCmdTask   RsyncTask     │
                                                                 │
                              ┌───────────┬───────────┬──────────┼─────────────┐
                              │           │           │          │             │
                              ▼           ▼           ▼          ▼             ▼
                         HttpChecker PortChecker PathChecker PathWatcher TimeWatcher
```

For now, we will focus on `CmdTask` and `Task`.

## Creating a `CmdTask`

CmdTask is one of the most commonly used Zrb Tasks. It helps you run any CLI command.

To define the CLI command, you can use `cmd` or `cmd_path` property.

Let's see some examples.

### Single Line CLI Command

Creating a CmdTask that runs a single-line CLI Command is easy. You can put your CLI Command into a `cmd` attribute.

```python
from zrb import runner, CmdTask

hello = CmdTask(
    name='hello',
    cmd='echo "hello"'
)
runner.register(hello)
```

### Multiline CLI Command

You can also put a list of multiline CLI commands into a `cmd` attribute by passing a list of strings representing the command.

For example, you can set `DBT_PROFILE` environment before invoking `dbt run`.

```python
from zrb import runner, CmdTask

run_dbt = CmdTask(
    name='run-dbt',
    cmd=[
        'export DBT_PROFILE=dbt-profile',
        'dbt run'
    ]
)
runner.register(run_dbt)
```

### Using External Shell Script

For short CLI commands, `cmd` is sufficient. But, when you have a very long CLI command, it is better to put the command into a separate shell script. Having an external shell script gives you several advantages:

- You get proper syntax highlighting when you open your shell script on your text editor.
- You can run your shell script independently.
- You can use your existing shell script.

Suppose you have the following shell script to run DBT.

```bash
# file-name: cmd/dbt-run.sh
export DBT_PROFILE=dbt_profile
dbt run
```

You can define your CmdTask as follows.

```python
from zrb import runner, CmdTask
import os

CURRENT_DIR = os.path.dirname(__file__)

run_dbt = CmdTask(
    name='run-dbt',
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'dbt-run.sh')
)
runner.register(run_dbt)
```

In the example, you use `cmd_path` instead of `cmd`. This practice allows you to define your workflow definition and the implementation separately.

## Creating a `Task`

Sometimes, you need to define your automation in Python. Python gives you better flexibility and modern paradigms compared to shell script.

To define your automation in Python, you can use `Task`. Let's see an example.

```python
from zrb import runner, Task

def print_hello(*args, **kwargs) -> str:
    return 'Hello world'

hello = Task(
    name='hello',
    run=print_hello
)
runner.register(hello)
```

In the example, you have a function named `print_hello`. This function accepts any arguments and returns a text.

To create a Task that runs a function, you have to ensure that the function accepts any arguments (i.e., having `*args` and `**kwargs` as its arguments).

Once you define your function, you then create a Task named `hello` and set its `run` attribute to `print_hello`.

Now, whenever you run `zrb hello`, you will get a `Hello world`.

## Creating a `Task` Using `@python_task` Decorator

`@python_task` decorator turn your function into a `Task`. This decorator is a syntactic sugar for `Task` class.

You can use `@python_task` decorator as follows.

```python
from zrb import runner, python_task

@python_task(
    name='hello',
    runner=runner
)
def hello(*args, **kwargs) -> str:
    return 'Hello world'
```

`@python_task` decorator has a `runner` parameter. You can use the parameter to register your Task.

Furthermore, `@python_task` turns `hello` into a `Task`. Thus, you can no longer treat it as a function (i.e., calling `hello()` won't work).

# Next

You have learned the basic building blocks of Zrb automation. Next, you can continue with [Task Lifecycle](task-lifecycle.md).

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
