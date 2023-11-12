🔖 [Table of Contents](README.md)

# Getting Started

Welcome to Zrb's getting started guide. We will cover everything you need to know to work with Zrb. In this article, you will learn about:

- [How to run a task](#running-a-task)
  - [Redirect task's output](#redirect-tasks-output)
  - [How tasks are organized](#how-tasks-are-organized)
  - [Getting available tasks/task groups](#getting-available-taskstask-groups)
  - [Using input prompts](#using-input-prompt)
- [How to create a project](#creating-a-project)
  - [Using/creating virtual environment](#activating-virtual-environment)
- [How to define a task](#creating-a-task)
  - [Scaffolding a task](#scaffolding-a-task)
  - [Updating task definition](#updating-task-definition)
    - [Common task parameters](#common-task-parameters)
    - [Cmd task parameters](#cmdtask-parameters)
    - [Python task parameters](#python_task-parameters)
- [How to define a long-running task]()

This guide assumes you have some familiarity with CLI and Python.

# Running a Task

Once you have installed Zrb, you can run some built-in tasks immediately. To run any Zrb task, you need to follow the following pattern:

```bash
zrb [task-groups...] <task-name> [task-parameters...]
```

For example, you want to run the `base64 encode` task with the following information:

- __Task group:__ base64
- __Task name:__ encode
- __Task parameters:__
  - `text` = `non-credential-string`

Based on the pattern, you will need to invoke the following command:

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

You can see that Zrb encoded `non-credential-string` into `bm9uLWNyZWRlbnRpYWwtc3RyaW5n`.

> __⚠️ WARNING:__ Base64 is a encoding algorithm that allows you to transform any characters into an alphabet which consists of Latin letters, digits, plus, and slash.
>
> Anyone can easily decode a base64-encoded string. __Never use it to encrypt your password or any important credentials!__

## Redirect Task's Output

You can use any task's output for further processing. For example, redirect a task's output and error into files.

```bash
zrb base64 encode --text "non-credential-string" > output.txt 2> stderr.txt
cat output.txt
cat stderr.txt
```

You can also use a task's output as other CLI command's parameter

```bash
echo $(zrb base64 encode --text "non-credential-string"  2> error.txt)
```

Finally, you can also use the pipe operator to redirect a task's output as other CLI command's input

```bash
zrb base64 encode --text "non-credential-string"  2> error.txt | lolcat
```

> __📝 NOTE:__ You can install lolcat by following [it's documentation](https://github.com/busyloop/lolcat). If you are using Linux, and you don't like `snap`, you can try to use your OS's package manager (e.g., `sudo apt install lolcat`)

## How Tasks are Organized

We usually put related `tasks` under the same `task-group`.

For example, we have two tasks under `base64` group:

- encode
- decode

Let's decode our base64-encoded text:

```bash
zrb base64 decode --text "bm9uLWNyZWRlbnRpYWwtc3RyaW5n"
```

You should get your original text back.

> __💡 HINT:__ You don't have to memorize any `task-group` or `task` name. The next two subsections will show you how to locate and execute any `task` without memorize anything.

## Getting Available Tasks/Task Groups

To see what `tasks`/`task-groups` are available, type `zrb` and press enter.

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
  base64              Base64 operations
  build               Build Zrb
  build-image         Build docker image
  build-latest-image  Build docker image
  devtool             Developer tools management
  env                 Environment variable management
  eval                Evaluate Python expression
  explain             Explain things
  git                 Git related commands
  install-symlink     Install Zrb as symlink
  md5                 MD5 operations
  playground          Playground related tasks
  process             Process related commands
  project             Project management
  publish             Publish new version
  publish-pip         Publish zrb to pypi
  publish-pip-test    Publish zrb to testpypi
  push-image          Push docker image
  push-latest-image   Push docker image
  serve-test          Serve zrb test result
  start-container     Run docker container
  stop-container      remove docker container
  test                Run zrb test
  ubuntu              Ubuntu related commands
  update              Update zrb
  version             Get Zrb version
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

Zrb will automatically prompt you to provide the parameter interactively.

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
> When prompts are disabled, Zrb will automatically use default values.

# Creating a project

To make things more manageable, you must put all related resources and task definitions under a `project`. A project is a directory containing `zrb_init.py`.

You can create a project manually or use Zrb's built-in task to generate the project. Suppose you want to create a project named `my-project`.

```bash
zrb project create --project-dir my-project --project-name my-project
```

Once invoked, you will have a directory named `my-project`. Let's see how the project looks like:

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

- `_automate`: This folder contains all your automation scripts and task definitions
- `src`: This folder contains all your resources like Docker compose file, helm charts, and source code.

When you make a project using `zrb project create` command, Zrb will generate a default `task-group` named `project`. This `task-group` contains some tasks to run/deploy everything. Try to type `zrb project` to see what tasks are available by default:

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

## Activating Virtual Environment

If you generate the project by invoking `zrb project create`, then you have to run the following command now:

```bash
source project.sh
```

The command will ensure that you work under the project's virtual environment.

If you create the project manually, you need to make a virtual environment for your project:

```bash
python -m venv .venv
source .venv/bin/activate
```

> __⚠️ WARNING:__ You have to make sure you are working under virtual environment everytime you work with Zrb project, either by invoking `source project.sh` or `source .venv/bin/activate`.


# Creating a Task

Zrb has a powerful command to create tasks under a project. Let's re-create the tasks we make in our [README.md](../README.md).

The goal of the tasks is to download any public CSV dataset and provide the statistical properties of the dataset. To do that, you need to:
- Ensure that you have Pandas installed on your machine
- Ensure that you have downloaded the dataset
- Run the Python script to get the statistical properties of the dataset

```
          🐼
 ┌──────────────────┐
 │                  │
 │  Install Pandas  ├─┐          📊
 │                  │ │  ┌─────────────────┐
 └──────────────────┘ └─►│                 │
                         │ Show Statistics │
 ┌──────────────────┐ ┌─►│                 │
 │                  │ │  └─────────────────┘
 │ Download Dataset ├─┘
 │                  │
 └──────────────────┘
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

We will modify the task later to match our use case.

You will also notice that Zrb automatically imports `_automate/show_stats.py` into `zrb_init.py`.

```python
import _automate._project as _project
import _automate.show_stats as show_stats
assert _project
assert show_stats
```

This modification allows you to invoke `show-stats` from the CLI

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

# 🐼 Define a task to install pandas
install_pandas = CmdTask(
    name='install-pandas',
    group=project_group,
    cmd='pip install pandas'
)

# Make install_pandas accessible from the CLI (i.e., zrb project install-pandas)
runner.register(install_pandas)

# ⬇️ Define a task to download dataset
download_dataset = CmdTask(
    name='download-dataset',
    group=project_group,
    inputs=[
        # Allow user to put the CSV dataset URL.
        StrInput(
            name='url',
            default='https://raw.githubusercontent.com/state-alchemists/datasets/main/iris.csv'
        )
    ],
    cmd='wget -O dataset.csv {{input.url}}'
)

# Make download_dataset accessible from the CLI (i.e., zrb project download-dataset)
runner.register(download_dataset)


# 📊 Define a task to show the statistics properties of the dataset
@python_task(
    name='show-stats',
    description='show stats',
    group=project_group,
    upstreams=[
      # Make sure install_pandas and download_dataset are successfully executed before running show_stats
      install_pandas,
      download_dataset
    ],
    runner=runner # Make show_stats accessible from the CLI (i.e., zrb project show-stats)
)
async def show_stats(*args: Any, **kwargs: Any) -> Any:
    import pandas as pd
    df = pd.read_csv('dataset.csv')
    return df.describe()
```

We define `install_pandas` and `download_dataset` using `CmdTask` since writing them using shell script is easier. We also make `show_stats` depend on `install_pandas` and `download_dataset` by defining `show_stats`'s upstream.

### Common Task Parameters

`CmdTask` and `@python_task` decorator has some parameters in common:

- __name__: The name of the task. When you invoke the task using the CLI, you need to use this name.
- __description__: The description of the task.
- __group__: The task group where the task belongs to
- __inputs__: The inputs and their default values.
  - If you are using a `CmdTask`, you can access the input using a Jinja Template (e.g., `{{input.input_name}}`)
  - If you are using a `@python_task` decorator, you can access the input by using `kwargs` argument (e.g., `kwargs.get('input_name')`)
- __upstreams__: Upstreams of the task. You can provide `AnyTask` as upstream.

### CmdTask Parameters

Aside from common task properties, `CmdTask` has other properties:

- __cmd__: String, or List of String, containing the shell script
- __cmd_path__: String, or List of String, containing the path to any shell scripts you want to use

### PythonTask Parameters

Aside from common task properties, `@python_task` has a runner parameter. This parameter is unique to `@python_task`. Any task created with `@python_task` with `runner` on it will be accessible from the CLI.

## Running show-stats

Finally, you can show the statistics property of any public CSV dataset quickly.

```
zrb project show-stats
```

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