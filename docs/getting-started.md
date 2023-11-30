🔖 [Table of Contents](README.md)

# Getting Started

Welcome to Zrb's getting started guide. We will cover everything you need to know to work with Zrb. In this article, you will learn about:

- [Installing Zrb](#installing-zrb)
- [Running a Task](#running-a-task)
  - [Understanding How Tasks are Organized](#understanding-how-tasks-are-organized)
  - [Getting Available Tasks/Task Groups](#getting-available-taskstask-groups)
  - [Using Input Prompts](#using-input-prompt)
- [Creating a Project](#creating-a-project)
  - [Activating Virtual Environment](#activating-virtual-environment)
- [Creating a Task](#creating-a-task)
  - [Scaffolding a Task](#scaffolding-a-task)
  - [Updating Task definition](#updating-task-definition)
- [Understanding The Code](#understanding-the-code)
    - [Task Definition](#task-definition)
      - [Creating a Task Using Task Classes](#creating-a-task-using-task-classes)
      - [Creating a Task Using Python Decorator](#creating-a-task-using-python-decorator)
    - [Task Parameters](#task-parameters)
    - [Task Inputs](#task-inputs)
    - [Task Environments](#task-environments)
    - [Switching Environment](#switching-environment)
- [Creating a Long-Running Task](#creating-a-long-running-task)

This guide assumes you have some familiarity with CLI and Python.

# Installing Zrb

First of all, you need to make sure you have Zrb installed on your computer.

You can install Zrb as a pip package by invoking the following command:

```bash
pip install zrb
```

Alternatively, you can also use our installation script to install Zrb along with `pyenv`:

```bash
curl https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh | bash
```

Check our [installation guide](./installation.md) for more information about the installation methods, including installing Zrb as a docker container.


# Running a Task

Once you have installed Zrb, you can run some built-in tasks immediately. To run any Zrb task, you need to follow the following pattern:

```bash
zrb [task-groups...] <task-name> [task-parameters...]
```

For example, you want to run the `base64 encode` task with the following properties:

- __Task group:__ base64
- __Task name:__ encode
- __Task parameters:__
  - __`text`__ = `non-credential-string`

In that case, you need to invoke the following command:

```bash
zrb base64 encode --text "non-credential-string"
```

```
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-10 09:08:33.183 ❁ 35276 → 1/1 🍎    zrb base64 encode • Completed in 0.051436424255371094 seconds
bm9uLWNyZWRlbnRpYWwtc3RyaW5n
To run again: zrb base64 encode --text "non-credential-string"
```

You can see how Zrb encoded `non-credential-string` into `bm9uLWNyZWRlbnRpYWwtc3RyaW5n`.

> __⚠️ WARNING:__ Base64 is a encoding algorithm that allows you to transform any characters into an alphabet which consists of Latin letters, digits, plus, and slash.
>
> Anyone can easily decode a base64-encoded string. __Never use it to encrypt your password or any important credentials!__

See our [tutorial](tutorials/integration-with-other-tools.md) to see how you can integrate Zrb with other CLI tools.

## Understanding How Tasks are Organized

By convention, we usually put related `tasks` under the same `task-group`.

For example, there two tasks under `base64` group. Both are dealing with base64 encoding/decoding algorithm:

```bash
zrb base64
```

```
Usage: zrb base64 [OPTIONS] COMMAND [ARGS]...

  Base64 operations

Options:
  --help  Show this message and exit.

Commands:
  decode  Decode a base64 encoded text
  encode  Encode a text using base64 algorithm
```

Now, let's try to decode our previously base64-encoded text:

```bash
zrb base64 decode --text "bm9uLWNyZWRlbnRpYWwtc3RyaW5n"
```

The command will return the original text (i.e., `non-credential-string`).

> __💡 HINT:__ You don't have to memorize any `task-group` or `task` name. The next two subsections will show you how to locate and execute any `task` without memorize anything.

## Getting Available Tasks/Task Groups

To see what `tasks`/`task-groups` are available under `zrb` command, you can type `zrb` and press enter.

```bash
zrb
```

```
Usage: zrb [OPTIONS] COMMAND [ARGS]...

                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   0.0.109
   _ _ . .  . _ .  _ . . .

Super framework for your super app.

☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst

Options:
  --help  Show this message and exit.

Commands:
  base64    Base64 operations
  devtool   Developer tools management
  env       Environment variable management
  eval      Evaluate Python expression
  explain   Explain things
  git       Git related commands
  md5       MD5 operations
  process   Process related commands
  project   Project management
  say       Say anything, https://www.youtube.com/watch?v=MbPr1oHO4Hw
  schedule  Show message/run command periodically
  ubuntu    Ubuntu related commands
  update    Update zrb
  version   Get Zrb version
  watch     Watch changes and show message/run command
```

You can then type `zrb [task-group...]` until you find the task you want to execute. For example, you can invoke the following command to see what tasks are available under `base64` group:

```bash
zrb base64
```

```
Usage: zrb base64 [OPTIONS] COMMAND [ARGS]...

  Base64 operations

Options:
  --help  Show this message and exit.

Commands:
  decode  Decode a base64 encoded text
  encode  Encode a text using base64 algorithm
```

> __📝 NOTE:__ A `task-group` might contains other `task-groups`

## Using input prompt

Once you find the task you want to execute, you can type `zrb [task-groups...] <task-name>` without bothering about `task-parameters`.

Zrb will ask you to provide the parameter interactively.

```bash
zrb base64 encode
```

```
Text []: non-credential-string
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-10 09:10:58.805 ❁ 35867 → 1/1 🍈    zrb base64 encode • Completed in 0.053427934646606445 seconds
bm9uLWNyZWRlbnRpYWwtc3RyaW5n
To run again: zrb base64 encode --text "non-credential-string"
```

> __📝 NOTE:__ If you need to disable prompt entirely, you can set `ZRB_SHOW_PROMPT` to `0` or `false`. Please refer to [configuration section](./configurations.md) for more information.
>
> When prompts are disabled, Zrb will automatically use task-input's default values.

# Creating a project

To make things more manageable, you must put all related resources and task definitions under a `project`. A project is a directory containing `zrb_init.py`.

You can create a project manually or use Zrb's built-in task to generate the project. Suppose you want to create a project named `my-project`. You can do so by invoking the following command:

```bash
zrb project create --project-dir my-project --project-name my-project
```

Once invoked, you will see a directory named `my-project`. Let's see what the project looks like:

```bash
cd my-project
ls -al
```

```
total 52
drwxr-xr-x  6 gofrendi gofrendi 4096 Nov 12 07:52 .
drwxr-xr-x 14 gofrendi gofrendi 4096 Nov 12 07:52 ..
drwxr-xr-x  7 gofrendi gofrendi 4096 Nov 12 07:52 .git
drwxr-xr-x  3 gofrendi gofrendi 4096 Nov 12 07:52 .github
-rw-r--r--  1 gofrendi gofrendi   27 Nov 12 07:52 .gitignore
-rw-r--r--  1 gofrendi gofrendi    7 Nov 12 07:52 .python-version
-rw-r--r--  1 gofrendi gofrendi 1937 Nov 12 07:52 README.md
drwxr-xr-x  3 gofrendi gofrendi 4096 Nov 12 07:52 _automate
-rwxr-xr-x  1 gofrendi gofrendi 1507 Nov 12 07:52 project.sh
-rw-r--r--  1 gofrendi gofrendi   13 Nov 12 07:52 requirements.txt
drwxr-xr-x  2 gofrendi gofrendi 4096 Nov 12 07:52 src
-rw-r--r--  1 gofrendi gofrendi  118 Nov 12 07:52 template.env
-rw-r--r--  1 gofrendi gofrendi   54 Nov 12 07:52 zrb_init.py
```

Every Zrb project has a file named `zrb_init.py` under the top-level directory. This file is your entry point to define your task definitions.

By convention, a project usually contains two sub-directories:

- ___automate__: This folder contains all your automation scripts and task definitions
- __src__: This folder contains all your resources like Docker compose file, helm charts, and source code.

When you make a project using `zrb project create` command, Zrb will generate a default `task-group` named `project`. This `task-group` contains some tasks to run/deploy your applications. Try to type `zrb project` to see what tasks are available by default:

```bash
zrb project
```

```
Usage: zrb project [OPTIONS] COMMAND [ARGS]...

  Project management

Options:
  --help  Show this message and exit.

Commands:
  add                Add resources to project
  build-images       Build project images
  create             create
  deploy             Deploy project
  destroy            Remove project deployment
  get-default-env    Get default values for project environments
  push-images        Build project images
  remove-containers  Remove project containers
  start              Start project
  start-containers   Start as containers
  stop-containers    Stop project containers
```


> __💡 HINT:__ To start working with Zrb, it is better to create a project. You can create a project by using `zrb project create` command, or by creating a file named `zrb_init.py`

## Activating Virtual Environment

Working in a virtual environment is recommended in most cases. This encapsulates your project pip packages, ensuring better independence and reproducibility.

### Activating Virtual Environment On A Generated Project

If you generate the project by invoking `zrb project create`, then you need to run the following command every time you start working on the project:

```bash
source project.sh
```

The command will activate the project's virtual environment and install necessary pip packages.

### Activating Virtual Environment On A Manually Created Project

If you create the project manually (i.e., by creating `zrb_init.py`),  you also need to make a virtual environment for your project. Creating a virtual environment is necessary if you work with non-standard Python libraries.

To create a virtual environment, you can invoke the following command:

```bash
python -m venv .venv
```

Once you make the virtual environment, you can activate it by invoking the following command:

```bash
source .venv/bin/activate
```

You need to run the command every time you start working on the project.


> __💡 HINT:__ Working with virtual environment is recommended whenever you work with any Python project, including Zrb project.


# Creating a Task

A task is the smallest unit of job definition. You can link your tasks together to form a more complex workflow.

Zrb has a powerful command to create tasks under a project. Let's re-create the tasks we make in our [README.md](../README.md).

The goal of the tasks is to download any public CSV dataset and provide the statistical properties of the dataset. To do that, you need to:

- Ensure that you have Pandas installed on your machine
- Ensure that you have downloaded the dataset
- Run the Python script to get the statistical properties of the dataset

```
       🐼
Install Pandas ─────┐           📊
                    ├──► Show Statistics
Download Datasets ──┘
       ⬇️
```

## Scaffolding a Task

Zrb has a powerful command to scaffold your project. To do so, you need to invoke the following command:

> __⚠️ WARNING:__ Make sure you have activate your virtual environment, either by invoking `source project.sh` or `source .venv/bin/activate`.

```bash
zrb project add python-task --project-dir "." --task-name "show-stats"
```

Once you invoke the command, Zrb will make a file named `_automate/show_stats.py`

```python
from typing import Any, Mapping
from zrb import Task, python_task, runner
from zrb.builtin.group import project_group

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='show-stats',
    description='show stats',
    group=project_group,
    runner=runner
)
async def show_stats(*args: Any, **kwargs: Any) -> Any:
    task: Task = kwargs.get('_task')
    env_map: Mapping[str, str] = task.get_env_map()
    input_map: Mapping[str, str] = task.get_input_map()
    task.print_out(f'Env map: {env_map}')
    task.print_out(f'Input map: {input_map}')
    return 'ok'
```

We will modify the task later to match our use case, but first let's check on `zrb_init.py`. You will notice how Zrb automatically imports `_automate/show_stats.py` into `zrb_init.py`.

```python
import _automate._project as _project
import _automate.show_stats as show_stats
assert _project
assert show_stats
```

This modification allows Zrb to load `show-stats` so that you can access it from the CLI

```
zrb project show-stats
```

## Updating Task Definition

To serve our use case, you need to add two more tasks:

- install-pandas
- download-dataset

You also need to ensure both of them are registered as `show-stats` upstreams. You also need to modify `show-stats` a little bit.

```python
from typing import Any
from zrb import CmdTask, python_task, StrInput, runner
from zrb.builtin.group import project_group
DEFAULT_URL = 'https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv'

# 🐼 Define a task named `install-pandas` to install pandas
# If this task failed, we want Zrb to retry it again 4 times at most.
install_pandas = CmdTask(
    name='install-pandas',
    group=project_group,
    cmd='pip install pandas',
    retry=4
)

# Make install_pandas accessible from the CLI (i.e., zrb project install-pandas)
runner.register(install_pandas)

# ⬇️ Define a task named `download-dataset` to download dataset
# This task has an input named `url`.
# The input will be accessible by using Jinja template: `{{input.url}}`
# If this task failed, we want Zrb to retry it again 4 times at most
download_dataset = CmdTask(
    name='download-dataset',
    group=project_group,
    inputs=[
        StrInput(name='url', default=DEFAULT_URL)
    ],
    cmd='wget -O dataset.csv {{input.url}}'
)

# Make download_dataset accessible from the CLI (i.e., zrb project download-dataset)
runner.register(download_dataset)


# 📊 Define a task to show the statistics properties of the dataset
# We use `@python_task` decorator since this task is better written in Python.
# This tasks depends on our previous tasks, `download_dataset` and `install_pandas`
# If this task failed, then it is failed. No need to retry
@python_task(
    name='show-stats',
    description='show stats',
    group=project_group,
    upstreams=[download_dataset, install_pandas],
    retry=0,
    runner=runner # Make show_stats accessible from the CLI (i.e., zrb project show-stats)
)
async def show_stats(*args: Any, **kwargs: Any) -> Any:
    import pandas as pd
    df = pd.read_csv('dataset.csv')
    return df.describe()
```

We define `install_pandas` and `download_dataset` using `CmdTask`. On the other hand, we use `@python_task` decorator to turn `show_stats` into a task.

Finally, we also set `install_pandas` and `download_dataset` as `show_stats`'s upstreams. This let Zrb gurantee that whenever you run `show_stats`, Zrb will always run `install_pandas` and `download_dataset` first.

To understand the code more, please visit [understanding the code section](#understanding-the-code).

## Running show-stats

Finally, you can show the statistics property of any public CSV dataset quickly.

```
zrb project show-stats
```

<details>
<summary>Show output</summary>

```
Url [https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv]:
🤖 ○ ◷ 2023-11-12 09:45:12.132 ❁ 43598 → 1/3 🐮 zrb project install-pandas • Run script: pip install pandas
🤖 ○ ◷ 2023-11-12 09:45:12.132 ❁ 43598 → 1/3 🐮 zrb project install-pandas • Working directory: /home/gofrendi/playground/my-project
🤖 ○ ◷ 2023-11-12 09:45:12.139 ❁ 43598 → 1/3 🍓 zrb project download-dataset • Run script: wget -O dataset.csv https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv
🤖 ○ ◷ 2023-11-12 09:45:12.139 ❁ 43598 → 1/3 🍓 zrb project download-dataset • Working directory: /home/gofrendi/playground/my-project
🤖 △ ◷ 2023-11-12 09:45:12.151 ❁ 43603 → 1/3 🍓 zrb project download-dataset • --2023-11-12 09:45:12--  https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv
🤖 △ ◷ 2023-11-12 09:45:12.218 ❁ 43603 → 1/3 🍓 zrb project download-dataset • Resolving raw.githubusercontent.com (raw.githubusercontent.com)... 185.199.111.133, 185.199.109.133, 185.199.110.133, ...
🤖 △ ◷ 2023-11-12 09:45:12.246 ❁ 43603 → 1/3 🍓 zrb project download-dataset • Connecting to raw.githubusercontent.com (raw.githubusercontent.com)|185.199.111.133|:443... connected.
🤖 △ ◷ 2023-11-12 09:45:12.803 ❁ 43603 → 1/3 🍓 zrb project download-dataset • HTTP request sent, awaiting response... 200 OK
🤖 △ ◷ 2023-11-12 09:45:12.806 ❁ 43603 → 1/3 🍓 zrb project download-dataset • Length: 4606 (4.5K) [text/plain]
🤖 △ ◷ 2023-11-12 09:45:12.808 ❁ 43603 → 1/3 🍓 zrb project download-dataset • Saving to: ‘dataset.csv’
🤖 △ ◷ 2023-11-12 09:45:12.810 ❁ 43603 → 1/3 🍓 zrb project download-dataset •
🤖 △ ◷ 2023-11-12 09:45:12.812 ❁ 43603 → 1/3 🍓 zrb project download-dataset •      0K ....                                                  100% 1.39M=0.003s
🤖 △ ◷ 2023-11-12 09:45:12.814 ❁ 43603 → 1/3 🍓 zrb project download-dataset •
🤖 △ ◷ 2023-11-12 09:45:12.816 ❁ 43603 → 1/3 🍓 zrb project download-dataset • 2023-11-12 09:45:12 (1.39 MB/s) - ‘dataset.csv’ saved [4606/4606]
🤖 △ ◷ 2023-11-12 09:45:12.817 ❁ 43603 → 1/3 🍓 zrb project download-dataset •
🤖 ○ ◷ 2023-11-12 09:45:12.978 ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: pandas in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (2.1.3)
🤖 ○ ◷ 2023-11-12 09:45:13.042 ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: numpy<2,>=1.22.4 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (1.26.1)
🤖 ○ ◷ 2023-11-12 09:45:13.044 ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: python-dateutil>=2.8.2 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (2.8.2)
🤖 ○ ◷ 2023-11-12 09:45:13.045 ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: pytz>=2020.1 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (2023.3.post1)
🤖 ○ ◷ 2023-11-12 09:45:13.047 ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: tzdata>=2022.1 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from pandas) (2023.3)
🤖 ○ ◷ 2023-11-12 09:45:13.049 ❁ 43601 → 1/3 🐮 zrb project install-pandas • Requirement already satisfied: six>=1.5 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from python-dateutil>=2.8.2->pandas) (1.16.0)
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-12 09:45:14.366 ❁ 43598 → 1/3 🍎 zrb project show-stats • Completed in 2.2365798950195312 seconds
       sepal_length  sepal_width  petal_length  petal_width
count    150.000000   150.000000    150.000000   150.000000
mean       5.843333     3.054000      3.758667     1.198667
std        0.828066     0.433594      1.764420     0.763161
min        4.300000     2.000000      1.000000     0.100000
25%        5.100000     2.800000      1.600000     0.300000
50%        5.800000     3.000000      4.350000     1.300000
75%        6.400000     3.300000      5.100000     1.800000
max        7.900000     4.400000      6.900000     2.500000
To run again: zrb project show-stats --url "https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv"
```
</details>

# Understanding The Code

## Task Definition

In general, there are two ways to define a task in Zrb.

- Using Task Classes (`CmdTask`, `DockerComposeTask`, `RemoteCmdTask`, `RsyncTask`, `ResourceMaker`, `FlowTask`, or `TriggeredTask`)
- Using Python Decorator (`@python_task`).

You can see that both `install_pandas` and `download_dataset` are instances of `CmdTask`, while `show_stats` is a decorated function.

### Creating a Task Using Task Classes

To define a task by using task classes, you need to follow this pattern:

```python
# importing zrb runner and the TaskClass
from zrb import runner, TaskClass

# Define a task, along with it's parameters
task_name = TaskClass(
    name='task-name',
    parameter=value,
    other_parameter=other_value
)

# regiter the task to zrb runner
runner.register(task_name)
```

There are several built-in task classes. Each with its specific use case:

- __CmdTask__: Run a CLI command/shell script.
- __DockerComposeTask__: Run any docker-compose related command (e.g., `docker compose up`, `docker compose down`, etc.)
- __RemoteCmdTask__: Run a CLI command/shell script on remote computers using SSH.
- __RSyncTask__: Copy file from/to remote computers using `rsync` command.
- __ResourceMaker__: Create resources (source code/documents) based on provided templates.
- __FlowTask__: Combine unrelated tasks into a single Workflow.
- __RecurringTask__: Create a long-running recurring task.

You can also create a custom task class as long as it fits `AnyTask` interface. The easiest way to ensure compatibility is by extending `BaseTask`. See our [tutorial](tutorials/extending-cmd-task.md) to see how we can create a new Task Class based on `CmdTask`.

### Creating a Task Using Python Decorator

To define a task by using Python decorator, you need to follow this pattern:

```python
# importing zrb runner and @python_task
from zrb import runner, python_task


# Decorate a function named `task_name`
@python_task(
    name='task-name',
    parameter=value,
    other_parameter=other_value,
    runner=runner # register the task to zrb runner
)
def task_name(*args, **kwargs):
    pass

# Note that python_task decorator turn your function into a task. So `task_name` is now a task, not a function.
```

Using `@python_task` decorator is your best choice if you need to write complex logic in Python.


## Task Parameters

Each task has its specific parameter. However, the following tasks are typically available:

- __name__: The name of the task. When you invoke the task using the CLI, you need to use this name. By convention, the name should-be written in `kebab-case` (i.e., separated by `-`)
- __description__: The description of the task.
- __group__: The task group where the task belongs to
- __inputs__: Task inputs and their default values.
- __envs__: Task's environment variables.
- __env_files__: Task's environment files.
- __upstreams__: Upstreams of the task. You can provide `AnyTask` as upstream.
- __checkers__: List of checker tasks. You usually need this for long-running tasks.
- __runner__: Only available in `@python_task`, the valid value is `zrb.runner`.

You can apply task parameters to both Task classes and `@python_task` decorator.

## Task Inputs

You can define task inputs using `StrInput`, `BoolInput`, `ChoiceInput`, `FloatInput`, `IntInput`, or `PasswordInput`.
To create an input, you need to provide some parameters:

- __name__: The name of the input. By convention, this should be kebab-cased (required).
- __default__: The default value of the input (optional, default: `None`).
- __should_render__: Whether the input should be rendered as Jinja template or not (optional, default: `True`).

For example, here you have an input named `message` with `Hello World` as the default value:

```python
from zrb import StrInput

message = StrInput(name='message', default='Hello World')
```

When you run a task with task inputs, Zrb will prompt you to override the input values. You can press `enter` if you want to use the default values.

### Using Task Inputs on CmdTask

To access the values of your inputs from your `CmdTask`, you can use Jinja template `{{ input.input_name }}`. Notice that you should use `snake_case` instead of `kebab-case` to refer to the input. Let's see the following example:

```python
from zrb import runner, CmdTask, StrInput

hello_cmd = CmdTask(
    name='hello-cmd',
    inputs=[
        StrInput(name='your-name', default='World')
    ],
    # Notice, we use {{input.your_name}} not {{input.your-name}} !!!
    cmd='echo Hello {{input.your_name}}'
)
runner.register(hello_cmd)
```

You can then run the task by invoking:

```bash
zrb hello-cmd
# or
zrb hello-cmd --your-name "John Wick"
```

### Using Task Inputs on @python_task Decorator

As for `@python_task`, you can use `kwargs` dictionary to get the input.

```python
from zrb import runner, python_task, StrInput

@python_task(
    name='hello-py',
    inputs=[
        StrInput(name='your-name', default='World')
    ],
    runner=runner
)
def hello_py(*args, **kwargs):
    # Notice, we use `your_name` instead of `your-name` !!!
    name = kwargs.get('your_name')
    return f'Hello {name}'
```


You can then run the task by invoking:

```bash
zrb hello-py
# or
zrb hello-py --your-name "John Wick"
```

## Task Environments

Aside from input, you can also define the `Task`'s environment variables using `Env` and `EnvFile`.

### Env

You can use `Env` to define a single environment variable for your Tasks. Typically, a Task could take multiple `Env`.

To create an `Env`, you need to provide some parameters:

- __name__: Name of the environment variable (required).
- __os_name__: Name of OS environment (optional, default=`None`)
    - if set to `None`, Zrb will link the environment variable to the OS environment.
    - if set to an empty string (i.e., `''`), Zrb will not link the environment variable to the OS's environment.
    - if set to a non-empty string, Zrb will link the environment variable to the OS's environment corresponding to this value.
- __default__: Default value of the environment variable (optional, default: `None`).
- __should_render__: Whether the environment variable should be rendered as a Jinja template (optional, default: `True`).


```python
from zrb import Env

env = Env(name='MESSAGE')
```

### EnvFile

`EnvFile` loads an environment file and uses its values as Task's environment variables. Typically a Task could take multiple `EnvFile`.

To create an `EnvFile`, you need to provide some parameters:

- __env_file__: Name of the environment file (required).
- __prefix__: Custom prefix for environment's os_name (optional, default=`None`)
- __should_render__: Whether the environment variable should be rendered as a Jinja template (optional, default: `True`).

```python
from zrb import EnvFile
import os

PROJECT_ENV = os.path.join(os.path.dirname(__file__), 'project.env')
env_file = EnvFile(env_file=PROJECT_ENV)
```

### Using Env and EnvFile

To use `EnvFile` in your tasks. Let's first create an environment file named `project.env`:

```bash
# file-name: project.env
SERVER_HOST=localhost
```

### Using Env and EnvFile on CmdTask

To access the values of your inputs from your `CmdTask`, you can use Jinja template `{{ env.ENV_NAME }}`.

```python
from zrb import runner, CmdTask, Env, EnvFile
import os

PROJECT_ENV = os.path.join(os.path.dirname(__file__), 'project.env')

hello_cmd = CmdTask(
    name='hello-cmd',
    envs=[
        Env(name='MESSAGE', default='Hello world'),
    ],
    env_files=[
        EnvFile(env_file=PROJECT_ENV)
    ],
    cmd=[
        'echo Message: {{env.MESSAGE}}',
        'echo Host: {{env.SERVER_HOST}}',
    ]
)
runner.register(hello_cmd)
```

You can then run the task by invoking:

```bash
zrb hello-cmd
```

It will give you the following results:

```
Message: Hello world
Host: localhost
```

### Using Env and EnvFile on @python_task Decorator

As for `@python_task`, you cannot use `os.getenv` to access task's environment. Instead, you should get the `task` instance from `kwargs`` and invoke `task.get_env_map()`.

```python
from zrb import runner, AnyTask, python_task, Env, EnvFile
import os

PROJECT_ENV = os.path.join(os.path.dirname(__file__), 'project.env')


@python_task(
    name='hello-py',
    envs=[
        Env(name='MESSAGE', default='Hello world'),
    ],
    env_files=[
        EnvFile(env_file=PROJECT_ENV)
    ],
    runner=runner
)
def hello_py(*args, **kwargs):
    task: AnyTask = kwargs.get('_task')
    env_map = task.get_env_map()
    message = env_map.get('MESSAGE')
    server_host = env_map.get('SERVER_HOST')
    return '\n'.join([
        f'Message: {message}',
        f'Host: {server_host}'
    ])
```

You can then run the task by invoking:

```bash
zrb hello-cmd
```

It will give you the following results:

```
Message: Hello world
Host: localhost
```

## Switching Environment

Zrb has a feature named environment cascading. This feature helps you switch between multiple environments (e.g., dev, staging, production).

To switch between environments, you can use `ZRB_ENV`

Let's go back to our previous example and set some environment variables:


```bash
export DEV_MESSAGE="Test Hello World"
export PROD_MESSAGE="Hello, Client"
export PROD_SERVER_HOST=stalchmst.com

zrb hello-cmd
```

Without `ZRB_ENV`, when you run the following commands, you will get the same outputs:

```
Message: Hello world
Host: localhost
```

Since we don't have `MESSAGE` and `HOST` on OS's environment variable, Zrb will use the default values.

### Dev Environment

Now, let's try this again with `DEV` environment:

```bash
export DEV_MESSAGE="Test Hello World"
export PROD_MESSAGE="Hello, Client"
export PROD_SERVER_HOST=stalchmst.com
export ZRB_ENV=DEV

zrb hello-cmd
```

Now, it will get the the following outputs:

```
Message: Test Hello World
Host: localhost
```

You see that now Zrb loads use `DEV_MESSAGE` value instead of the default `Hello World`.

However, since Zrb cannot find `DEV_SERVER_HOST`, it use the default value `localhost`.

### Prod Environment

Now let's try again with `PROD` environment:

```bash
export DEV_MESSAGE="Test Hello World"
export PROD_MESSAGE="Hello, Client"
export PROD_SERVER_HOST=stalchmst.com
export ZRB_ENV=PROD

zrb hello-cmd
```

Now, since Zrb can find both `PROD_MESSAGE` and `PROD_SERVER_HOST`, Zrb will show the following output:

```
Message: Hello, Client
Host: stalchmst.com
```

# Creating a long-running task

Commonly, you can determine whether a task is successful/failed after it is completed. However, some tasks might run forever, and you can only see whether the task is completed or failed by checking other behaviors. For example, a web server is successfully running if you can get the expected HTTP response from the server.

Zrb has some checking mechanisms to handle this use case.

Let's start by scaffolding a CmdTask named `run-jupyterlab`.

```bash
zrb project add cmd-task --project-dir "." --task-name "run-jupyterlab"
```

Once you do so, you can start modifying `_automate/`

In some cases, your task has to run forever (i.e., web server).

Arasaka is a data-driven (and family-driven) company. They need their data scientists to experiment a lot to present the most valuable information/knowledge.

For this, they need to be able to create a lot of notebooks for experimentation.

To make sure things work, you need to:
- Install jupyterlab.
- Add Jupyterlab to your `requirements.txt`.
- Create a `notebooks` directory under `src`.
- Create a `start-jupyter` task.

Let's start by installing jupyterlab

```bash
pip install jupyterlab
```

Once jupyterlab has been installed, you need to add it into requirements.txt. You can do so by typing `pip freeze | grep jupyterlab` and add the output to your `requirements.txt`. Or you can do it with a single command:

```bash
pip freeze | grep jupyterlab >> requirements.txt
```

Now let's make a `notebooks` directory under `src`.

```bash
mkdir -p src/notebooks
touch src/notebooks/.gitkeep
```

You need an empty `.gitkeep` file, to tell git to not ignore the directory.

## Adding start-jupyterlab

We have a few requirements for `start-jupyterlab` task

- You should show Arasaka banner before starting jupyterlab.
- `start-jupyterlab` is considered completed only if the port is accessible.
- Arasaka employee can choose the port to serve jupyterlab in their computer.

Let's start by adding the task to your project.

```bash
zrb project add cmd-task --project-dir . --task-name start-jupyterlab
```

Now, let's modify `_automate/start_jupyterlab.py` into the following:

```python
from zrb import CmdTask, PortChecker, IntInput, runner
from zrb.builtin.group import project_group
import os


install_jupyterlab = CmdTask(
    name='install-jupyterlab',
    group=project_group,
    cmd='pip install jupyterlab'
)
runner.register(install_jupyterlab)


notebook_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'src'
)
run_jupyterlab = CmdTask(
    name='run-jupyterlab',
    description='run jupyterlab',
    group=project_group,
    upstreams=[install_jupyterlab],
    inputs=[
        IntInput(name='jupyterlab-port', default=8080),
    ],
    cmd=[
        'jupyter lab \\',
        '  --port {{input.jupyterlab_port}}',
        f'  --notebook-dir "{notebook_path}"'
    ],
    checkers=[
        PortChecker(name='check-jupyterlab', port='{{input.jupyterlab_port}}')
    ]
)
runner.register(run_jupyterlab)
```

You may notice that `run_jupyterlab` has a `PortChecker` on it. If the `PortChecker` can get TCP response, then `run_jupyterlab` is considered successful.
Let's run the task:

```bash
zrb project run-jupyterlab
```

```
Jupyterlab port [8080]: 
🤖 ○ ◷ 2023-11-12 10:26:32.759 ❁ 58728 → 1/3 🐨 zrb project install-jupyterlab • Run script: pip install jupyterlab
🤖 ○ ◷ 2023-11-12 10:26:32.759 ❁ 58728 → 1/3 🐨 zrb project install-jupyterlab • Working directory: /home/gofrendi/playground/my-project
🤖 ○ ◷ 2023-11-12 10:26:33.109 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: jupyterlab in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (4.0.8)
🤖 ○ ◷ 2023-11-12 10:26:33.149 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: async-lru>=1.0.0 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from jupyterlab) (2.0.4)
🤖 ○ ◷ 2023-11-12 10:26:33.151 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: ipykernel in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from jupyterlab) (6.26.0)
🤖 ○ ◷ 2023-11-12 10:26:33.153 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: jinja2>=3.0.3 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from jupyterlab) (3.1.2)
🤖 ○ ◷ 2023-11-12 10:26:33.156 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: jupyter-core in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from jupyterlab) (5.5.0)
🤖 ○ ◷ 2023-11-12 10:26:33.968 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: pycparser in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from cffi>=1.0.1->argon2-cffi-bindings->argon2-cffi->jupyter-server<3,>=2.4.0->jupyterlab) (2.21)
🤖 ○ ◷ 2023-11-12 10:26:34.041 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: arrow>=0.15.0 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from isoduration->jsonschema[format-nongpl]>=4.18.0->jupyter-events>=0.6.0->jupyter-server<3,>=2.4.0->jupyterlab) (1.3.0)
🤖 ○ ◷ 2023-11-12 10:26:34.093 ❁ 58731 → 1/3 🐨 zrb project install-jupyterlab • Requirement already satisfied: types-python-dateutil>=2.8.10 in /home/gofrendi/zrb/.venv/lib/python3.10/site-packages (from arrow>=0.15.0->isoduration->jsonschema[format-nongpl]>=4.18.0->jupyter-events>=0.6.0->jupyter-server<3,>=2.4.0->jupyterlab) (2.8.19.14)
🤖 ○ ◷ 2023-11-12 10:26:34.717 ❁ 58728 → 1/3 🐹 zrb project run-jupyterlab • Run script:
        0001 | jupyter lab \
        0002 |   --port 8080
        0003 |   --notebook-dir "/home/gofrendi/playground/my-project/src"
🤖 ○ ◷ 2023-11-12 10:26:34.717 ❁ 58728 → 1/3 🐹 zrb project run-jupyterlab • Working directory: /home/gofrendi/playground/my-project
🤖 △ ◷ 2023-11-12 10:26:35.693 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab • [I 2023-11-12 10:26:35.675 ServerApp] Use Control-C to stop this server and shut down all kernels (twice to skip confirmation).
🤖 △ ◷ 2023-11-12 10:26:36.789 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab • [C 2023-11-12 10:26:36.788 ServerApp]
🤖 △ ◷ 2023-11-12 10:26:36.791 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab •
🤖 △ ◷ 2023-11-12 10:26:36.793 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab •     To access the server, open this file in a browser:
🤖 △ ◷ 2023-11-12 10:26:36.795 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab •         file:///home/gofrendi/.local/share/jupyter/runtime/jpserver-58922-open.html
🤖 △ ◷ 2023-11-12 10:26:36.798 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab •     Or copy and paste one of these URLs:
🤖 △ ◷ 2023-11-12 10:26:36.799 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab •         http://localhost:8080/lab?token=58eecd6aa4a56445ecf8b8d8c2f2148d47a7ce8456ecd680
🤖 △ ◷ 2023-11-12 10:26:36.801 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab •         http://127.0.0.1:8080/lab?token=58eecd6aa4a56445ecf8b8d8c2f2148d47a7ce8456ecd680
🤖 ○ ◷ 2023-11-12 10:26:36.807 ❁ 58728 → 1/1 🐹     check-jupyterlab • Checking localhost:8080 (OK)
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-12 10:26:36.807 ❁ 58920 → 1/3 🐹 zrb project run-jupyterlab • Completed in 4.050489664077759 seconds
```

Open up your browser on [http://localhost:8080](http://localhost:8080) to start working with the notebook.

# Now you are ready

We have covered everything you need to know to work with Zrb.

To learn more about tasks and other concepts, you can visit [Zrb concept section](concepts/README.md).

Also, do you know that you can make and deploy a CRUD application without even touching your IDE/text editor? Check out [our tutorials](tutorials/README.md) for more cool tricks.


🔖 [Table of Contents](README.md)