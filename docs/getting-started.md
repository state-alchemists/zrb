🔖 [Table of Contents](README.md)

<div align="center">
  <img src="_images/emoji/checkered_flag.png"/>
  <p>
    <sub>
      Let's get started
    </sub>
  </p>
</div>

# Getting Started

Welcome to Zrb's getting started guide. We will cover everything you need to know to work with Zrb. In this Getting Started Guide, you will learn about:

- [Installing Zrb](#installing-zrb)
- [Running a Task](#running-a-task)
  - [How Tasks are Organized](#how-tasks-are-organized)
  - [Getting Available Tasks/Task Groups](#getting-available-taskstask-groups)
  - [Using Interactive Mode](#using-interactive-mode)
- [Creating a Project](#creating-a-project)
  - [Using `project.sh`](#using-projectsh)
- [Creating a Task](#creating-a-task)
    - [Task Definition](#task-definition)
    - [Common Task Properties](#common-task-properties)
    - [Task Dependencies](#task-dependencies)
    - [Task Inputs](#task-inputs)
    - [Task Environments](#task-environments)
    - [Environment Cascading](#environment-cascading)
    - [Basic Example](#basic-example)
    - [Advance Example](#advance-example-long-running-task)

This guide assumes you have some familiarity with CLI and Python.

# Installing Zrb

<div align="center">
  <img src="_images/emoji/wrench.png"/>
  <p>
    <sub>
      Installation: Let's put this into your machine.
    </sub>
  </p>
</div>

Before working with Zrb, you must ensure you have Zrb installed on your system.

If you are working on a new computer, the following command will help you install Zrb and Pyenv:

```bash
# On a new computer
curl https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh | bash
```

If you already have your own Python Ecosystem (i.e., [Pyenv](https://github.com/pyenv/pyenv), [Conda](https://docs.conda.io/en/latest), or Venv), you can install Zrb as a Python package using the Pip command.

```bash
# On a computer with its own Python ecosystem.
pip install zrb
```

Alternatively, you can also install Zrb as a container. Please see the [installation guide](./installation.md) for more detailed instructions.


# Running a Task


<div align="center">
  <img src="_images/emoji/runner.png"/>
  <p>
    <sub>
      <a href="https://www.youtube.com/watch?v=2wVPyo_hnWw" target="blank">Run! run! run!</a>
    </sub>
  </p>
</div>

Zrb comes with some built-in task definitions. To run a Zrb task, you need to follow the following pattern:

```bash
zrb [task-groups...] <task-name> [task-parameters...]
```

Let's see the following example:

```bash
 zrb base64 encode --text "non-credential-string"
       │      │    └──────────────┬─────────────┘                            
       │      │                   │ 
       ▼      │                   ▼
   task-group │            task-parameter
              │
              ▼
          task-name
```

You will see how Zrb encoded `non-credential-string` into `bm9uLWNyZWRlbnRpYWwtc3RyaW5n`.

```
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-10 09:08:33.183 ❁ 35276 → 1/1 🍎    zrb base64 encode • Completed in 0.051436424255371094 seconds
bm9uLWNyZWRlbnRpYWwtc3RyaW5n
To run again: zrb base64 encode --text "non-credential-string"
```

Like any CLI program, when you run a Zrb task, you get two kinds of outputs:

- `Standard Error (stdout)`: Contains logs, error messages, and other information.
- `Standard Output (stderr)`: Contains the output of the program.

In our previous example, Zrb will put `bm9uLWNyZWRlbnRpYWwtc3RyaW5n` into `Standard Output` and everything else into `Standard Error`. You will need this information if you want to [integrate Zrb with other tools](tutorials/integration-with-other-tools.md)

> __⚠️ WARNING:__ Base64 is a encoding algorithm that allows you to transform any characters into an alphabet which consists of Latin letters, digits, plus, and slash.
>
> Anyone can easily decode a base64-encoded string. __Never use it to encrypt your password or any important credentials!__

## How Tasks are Organized

<div align="center">
  <img src="_images/emoji/file_cabinet.png"/>
  <p>
    <sub>
      Put related Tasks under the same Group for better discoverability.
    </sub>
  </p>
</div>

Hierarchically speaking, you can think of Task Groups as directories and Tasks as files.

That means that a Task Group might contain:

- Other Task Groups
- One or more Tasks

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
├── env
│   └── get
├── eval
├── explain
│   ├── dry-principle
│   ├── kiss-principle
│   ├── solid-principle
│   ├── ...
│   └── zen-of-python
├── git
├── ...
└── watch-changes
```

When you type `zrb` in your terminal, you will see top-level Tasks and Task Groups. You can then type the Task Group or the Task until you find what you need.

Let's try it.

```bash
zrb
```

```
Usage: zrb [OPTIONS] COMMAND [ARGS]...

                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   0.1.0
   _ _ . .  . _ .  _ . . .

Super framework for your super app.

☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst

Options:
  --help  Show this message and exit.

Commands:
  base64         Base64 operations
  coba           coba
  devtool        Developer tools management
  env            Environment variable management
  eval           Evaluate Python expression
  explain        Explain things
  git            Git related commands
  md5            MD5 operations
  process        Process related commands
  project        Project management
  say            Say anything, https://www.youtube.com/watch?v=MbPr1oHO4Hw
  schedule       Show message/run command periodically
  ubuntu         Ubuntu related commands
  update         Update zrb
  version        Get Zrb version
  watch-changes  Watch changes and show message/run command
```

You see that Zrb has many Tasks and Task Groups. Now, let's take a look at `base64` Group.

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

You will find two tasks (i.e., `decode` and `encode`) under the `base64` group.

## Using Interactive Mode

<div align="center">
  <img src="_images/emoji/speech_balloon.png"/>
  <p>
    <sub>
      Most life issues are just communication problems in disguise.
    </sub>
  </p>
</div>

You have seen how you can set the Task Parameters by using CLI options as follows:

```bash
zrb base64 encode --text "non-credential-string"
```

The CLI Options are optional. You can run the task without specifying the options. When you do so, Zrb will activate the interactive mode so that you can supply the parameter values on the run.

Let's try it.

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

> __📝 NOTE:__ You can disable the interactive mode by setting `ZRB_SHOW_PROMPT` to `0` or `false`. Please refer to [configuration section](./configurations.md) for more information.
>
> When prompts are disabled, Zrb will automatically use task-parameter's default values.

That's it. That's all you need to know to work with Zrb.

In the rest of this section, you will learn about Zrb project and how to make your own Zrb Tasks.

# Creating A Project

<div align="center">
  <img src="_images/emoji/building_construction.png"/>
  <p>
    <sub>
      A project is like a fridge light; it only works when you open it to check.
    </sub>
  </p>
</div>

You probably want to organize your jobs under multiple projects to keep them separated.

At its basic, a project is a directory containing a single file named `zrb_init.py`. This setup is probably sufficient for a simple hello-world project.

To make something more than a simple hello-world, you better use `zrb project create` command.

```bash
zrb project create --project-dir my-project --project-name my-project
```

Once invoked, you will see a project named `my-project`. Let's see what this project looks like:

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

Every Zrb project has a file named `zrb_init.py` under the top-level directory. This file is your entry point to define your Task definitions.

By convention, a project usually contains two sub-directories:

- ___automate__: This folder contains all your automation scripts and task definitions
- __src__: This folder contains all your resources like Docker compose file, helm charts, and source code.

Moreover, Zrb provides some built-in Tasks under `project` Task Group. As always, you can invoke `zrb project` to see those tasks.

## Using `project.sh`

When you create a project using `zrb project create` command, you will find a file named `project.sh`. This script file helps you to load the virtual environment, install requirements, and activate shell completion.

To use the script, you need to invoke the following command:

```bash
source project.sh
```

Anytime you start working on your project, you should load `project.sh`.

# Creating A Task

<div align="center">
  <img src="_images/emoji/clipboard.png"/>
  <p>
    <sub>
      Finishing a task: 10% skill, 90% not getting distracted by the internet.
    </sub>
  </p>
</div>

Tasks are your most negligible unit of job definition.

Zrb has multiple Task Types, including `CmdTask`, `python_task`, `DockerComposeTask`, `FlowTask`, `RecurringTask`, `RemoteCmdTask`, `RsyncTask`, `ResourceMaker`, etc.

Typically, a Zrb Task has multiple settings:

- Retry mechanism
- Task Upstreams
- Task Environment and Environment File
- Task Input/Parameter 
- Readiness Checker

## Task Definition

<div align="center">
  <img src="_images/emoji/sparkles.png"/>
  <p>
    <sub>
      And then there was light.
    </sub>
  </p>
</div>

There are two ways to create a Zrb Task:

- __Using Task Class__ (e.g., `CmdTask`, `DockerComposeTask`, `FlowTask`, `RecurringTask`, `RemoteCmdTask`, `RsyncTask`, `ResourceMaker`, etc)
- __Using `@python_task` decorator__

### Using Task Class

You can use Task Class as follows:

```python
variable_name = TaskClass(
    name='task-name',
    # other_task_property=some_value,
    # ...
)
```

Each Task Class handles a specific use case. For example, you can use `CmdTask` to run a shell script, but it is better to use `DockerComposeTask` for docker-compose-related jobs.

Here is a quick list to see which class is better for what:

- __Task__: General purpose class, usually created using `@python_task` decorator.
- __CmdTask__: Run a CLI command/shell script.
- __DockerComposeTask__: Run any docker-compose related command (e.g., `docker compose up`, `docker compose down`, etc.)
- __RemoteCmdTask__: Run a CLI command/shell script on remote computers using SSH.
- __RSyncTask__: Copy file from/to remote computers using `rsync` command.
- __ResourceMaker__: Create resources (source code/documents) based on provided templates.
- __FlowTask__: Combine unrelated tasks into a single Workflow.
- __RecurringTask__: Create a long-running recurring task.


### Using `@python_task` decorator

`@python_task` decorator is a syntactic sugar for `Task` class. You can use the decorator as follows:

```python
@python_task(
    name='task-name,
    # other_task_property=some_value,
    # ...
)
def function_name(*args, **kwargs):
    pass
```

`@python_task` decorator turns your function into a `Task`.

## Common Task Properties

<div align="center">
  <img src="_images/emoji/house.png"/>
  <p>
    <sub>
      Property buying: where Monopoly meets your real bank balance.
    </sub>
  </p>
</div>

The following properties are usually available:

- __name__: The name of the task. When you invoke the task using the CLI, you need to use this name. By convention, the name should-be written in `kebab-case` (i.e., separated by `-`)
- __description__: The description of the task.
- __group__: The task group where the task belongs to
- __inputs__: Task inputs and their default values.
- __envs__: Task's environment variables.
- __env_files__: Task's environment files.
- __retry__: How many time to retry the execution before entering `Failed` state.
- __upstreams__: Upstreams of the task. You can provide `AnyTask` as upstream.
- __checkers__: List of checker tasks. You usually need this for long-running tasks.
- __runner__: Only available in `@python_task`, the valid value is `zrb.runner`.


## Task Dependencies

<div align="center">
  <img src="_images/emoji/chicken.png"/>
  <img height="50em" src="_images/emoji/baby_chick.png">
  <img height="50em" src="_images/emoji/baby_chick.png">
  <img height="50em" src="_images/emoji/baby_chick.png">
  <p>
    <sub>
      Followers are like shadows: bigger in the spotlight.
    </sub>
  </p>
</div>

There are two ways to define task dependencies in Zrb.

- Using shift-right (i.e., `>>`) operator.
- Using `upstreams` parameter.

By defining dependencies, you can ensure that Zrb will wait for your upstreams to be ready before proceeding with the main task.

You can use `>>` operator as follows:

```python
task_1 = CmdTask(name='task-1')
task_2 = CmdTask(name='task-2')
task_3 = CmdTask(name='task-3')
task_4 = CmdTask(name='task-4')
task_5 = CmdTask(name='task-5')
task_6 = CmdTask(name='task-6')

task_1 >> Parallel(task_2, task_3) >> Parallel(task_4, task_5) >> task_6
```

Or you can use `upstreams` parameter as follows:

```python
task_1 = CmdTask(name='task-1')
task_2 = CmdTask(name='task-2', upstreams=[task_1])
task_3 = CmdTask(name='task-3', upstreams=[task_1])
task_4 = CmdTask(name='task-4', upstreams=[task_2, task_3])
task_5 = CmdTask(name='task-5', upstreams=[task_2, task_3])
task_6 = CmdTask(name='task-6', upstreams=[task_4, task_5])
```

## Task Inputs

<div align="center">
  <img src="_images/emoji/abcd.png"/>
  <p>
    <sub>
      Input: where your program politely asks, 'What's the magic word?
    </sub>
  </p>
</div>


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

### Using Task Inputs on Task Class

To access the values of your inputs in your Task Properties, you can use Jinja template `{{ input.input_name }}`. Notice that you should use `snake_case` instead of `kebab-case` to refer to the input. Let's see the following example:

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

### Using Task Inputs on `@python_task` Decorator

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

<div align="center">
  <img src="_images/emoji/palm_tree.png"/>
  <p>
    <sub>
      Save the Earth. It's the only planet with chocolate!
    </sub>
  </p>
</div>

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

<div align="center">
  <img src="_images/emoji/desert_island.png"/>
  <p>
    <sub>
      An island is just a sea's attempt at a mountain peak joke.
    </sub>
  </p>
</div>

`EnvFile` loads an environment file and uses its values as Task's environment variables. Typically a Task could take multiple `EnvFile`.

To create an `EnvFile`, you need to provide some parameters:

- __env_file__: Name of the environment file (required).
- __prefix__: Custom prefix for environment's os_name (optional, default=`None`)
- __should_render__: Whether the environment variable should be rendered as a Jinja template (optional, default: `True`).

```python
from zrb import EnvFile
import os

PROJECT_ENV = os.path.join(os.path.dirname(__file__), 'project.env')
env_file = EnvFile(path=PROJECT_ENV)
```

### Using Env and EnvFile

To use `EnvFile` in your tasks. Let's first create an environment file named `project.env`:

```bash
# file-name: project.env
SERVER_HOST=localhost
```

### Using Env and EnvFile on Task Class

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
        EnvFile(path=PROJECT_ENV)
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

### Using Env and EnvFile on `@python_task` Decorator

As for `@python_task`, you cannot use `os.getenv` to access task's environment. Instead, you should get the `task` instance from `kwargs` and invoke `task.get_env_map()`.

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
        EnvFile(path=PROJECT_ENV)
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

## Environment Cascading

Zrb has a feature named environment-cascading. In short, it can help you to switch between `DEV`, `PROD`, or `STAGING` based on `ZRB_ENV` value.

For example, suppose we have the following task:

```python
show_db_url = Cmdtask(
    name='show-db-url',
    envs=[
        Env(name='DB_URL')
    ],
    cmd='echo {{ env.DB_URL }}'
)
runner.register(show_db_url)
```

The task is doing a simple job, showing the value of `DB_URL`.

Now let's consider the following environment variables:

```bash
export DB_URL=postgresql://root:toor@localhost
export PROD_DB_URL=postgresql://prod-user:somePassword@db.my-company.com
```

As expected, when you run `zrb show-db-url`, you will get the value of `DB_URL` (i.e., `postgresql://root:toor@localhost`)

__Using PROD Environment__

Now, let's set `ZRB_ENV` to `PROD`.

```bash
export ZRB_ENV=PROD
zrb show-db-url
```

You will see Zrb automatically uses the value of `PROD_DB_URL` (i.e., `postgresql://prod-user:somePassword@db.my-company.com`)

__Using DEV Environment__

Let's try it again with `DEV` environment

```bash
export ZRB_ENV=DEV
zrb show-db-url
```

Now, since Zrb cannot find `DB_DB_URL`, it will use the `DB_URL` instead (i.e., `postgresql://prod-user:somePassword@db.my-company.com`)

By using this behavior, you can work on multiple environment with the same codebase.


## Basic Example

<div align="center">
  <img src="_images/emoji/feet.png"/>
  <p>
    <sub>
      One small step for a man, one giant leap for mankind.
    </sub>
  </p>
</div>

```python
from zrb import runner, Parallel, Task, CmdTask, python_task, Env, StrInput

# Define first task
hello_cmd = CmdTask(
    name='hello-cmd',
    envs=[
        Env(name='MODE', default='DEV')
    ],
    inputs=[
        StrInput(name='user-name', default='Tom')
    ],
    cmd='echo "Hello, {{ input.user_name }}. Current mode: {{ env.MODE }}"'
)

# Define second task
@python_task(
    name='hello-py',
    envs=[
        Env(name='MODE', default='DEV')
    ],
    inputs=[
        StrInput(name='user-name', default='Tom')
    ]
)
def hello_py(*args, **kwargs) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    user_name = kwargs.get('user_name')
    mode = env_map.get('MODE')
    task.print_out(f'Hello, {user_name}. Current mode: {mode}')

# Define third task along with it's dependencies
hello = Task(name='hello')
Parallel(hello_cmd, hello_py) >> hello

# Register tasks to runner
runner.register(hello, hello_cmd, hello_py)
```

In the example, we have three task definitions:

- `hello-cmd`
- `hello-py`
- `hello`

We also set `hello-cmd` and `hello-py` as `hello`'s dependencies. That means Zrb will always wait for `hello-cmd` and `hello-py` readiness before proceeding with `hello`.

Finally, by invoking `runner.register(hello, hello_cmd, hello_py)`; we want the tasks to be available from the CLI.

> __⚠️ WARNING:__ Notice how `user-name` input is retrieved as `{{ input.user_name }}` or `kwargs.get('user_name')`. Zrb automatically translate the input name into `snake_case` since Python doesn't recognize `kebab-case` as valid variable name.

<details>

<summary>👉 <b>Click here to break down the code</b> 👈</summary>

### Import Statement

<div align="center">
  <img src="_images/emoji/truck.png"/>
  <p>
    <sub>
      <a href="https://xkcd.com/353/" target="blank">import antigravity.</a>
    </sub>
  </p>
</div>

```python
from zrb import runner, Parallel, Task, CmdTask, python_task, Env, StrInput
```

At the very beginning, we import some resources from `zrb` package:

- `runner`: We need Zrb runner to register our tasks and make them available from the CLI.
- `Parallel`: We need this class to define concurrent dependencies.
- `Task`: We need this class to create a simple Zrb Task. We can also use this class for type-hint.
- `CmdTask`: We need this class to create a shell script Task.
- `python_task`: We need this class to create a Python Task.
- `Env`: We need this class to define Task Environments.
- `StrInput`: We need this class to define Task Input/Parameter.

### `hello-cmd` Definition

<div align="center">
  <img src="_images/emoji/shell.png"/>
  <p>
    <sub>
      Shell Script: Every problem is a line of code away from being solved.
    </sub>
  </p>
</div>

```python
hello_cmd = CmdTask(
    name='hello-cmd',
    envs=[
        Env(name='MODE', default='DEV')
    ],
    inputs=[
        StrInput(name='user-name', default='Tom')
    ],
    cmd='echo "Hello, {{ input.user_name }}. Current mode: {{ env.MODE }}"'
)
```

`hello-cmd` is a `CmdTask`. It has an environment variable named `MODE` and a parameter named `user-name`.

To access the value of `MODE` environment, we can use `{{ env.MODE }}`.

Meanwhile, to access the value of `user-name` parameter, we can use `{{ input.user_name }}`. Notice how Zrb translates the input name into `snake_case`.

### `hello-py` Definition

<div align="center">
  <img src="_images/emoji/snake.png"/>
  <p>
    <sub>
      Python: This should be the programming language, not the snake.
    </sub>
  </p>
</div>

```python
@python_task(
    name='hello-py',
    envs=[
        Env(name='MODE', default='DEV')
    ],
    inputs=[
        StrInput(name='user-name', default='Tom')
    ]
)
def hello_py(*args, **kwargs) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    user_name = kwargs.get('user_name')
    mode = env_map.get('MODE')
    task.print_out(f'Hello, {user_name}. Current mode: {mode}')
```

`hello-py` is a Python Task. Like `hello-cmd`, it has an environment variable named `MODE` and a parameter named `user-name`.

We use `@python_task` decorator to turn `hello_py` into a Task.

`hello_py` function takes a keyword argument `kwargs`. You can see that `Zrb` automatically inject the inputs as keyword arguments. Additionally, the keyword argument also contains a `_task` object, representing the current task.

You can retrieve `user-name` input value by from the `kwargs` argument as follow:

```python
user_name = kwargs.get('user_name')
```

Meanwhile, to access the value of `MODE` environment you cannot use `os.getenv` or `os.environ`. Instead, you should retrieve the task first and get the environment map:

```python
task: Task = kwargs.get('_task')
env_map = task.get_env_map()
mode = env_map.get('MODE')
```

### `hello` Definition And Its Dependencies


<div align="center">
  <img src="_images/emoji/pill.png"/>
  <p>
    <sub>
      Adding a new dependency is like inviting a stranger to live in your codebase.
    </sub>
  </p>
</div>

```python
hello = Task(name='hello')
Parallel(hello_cmd, hello_py) >> hello
```

`hello` is a simple Zrb Task. This task wraps our two previous tasks into a single command.

You can use the shift-right operator (i.e., `>>`) to define the dependencies. In this example, we want `hello` to depend on `hello-py` and `hello-cmd`. Thus, we can expect Zrb to run `hello-py` and `hello-cmd` before proceeding with `hello`.

```
hello-py ───┐
            ├─► hello
hello-cmd ──┘
```

### Register Tasks to The `runner`

<div align="center">
  <img src="_images/emoji/page_facing_up.png"/>
  <p>
    <sub>
      Fotokopi KTP dan biaya registrasi lima ribu rupiah.
    </sub>
  </p>
</div>


```python
runner.register(hello, hello_cmd, hello_py)
```

Finally, we want `hello`, `hello-cmd`, and `hello-py` to be available from the CLI. By registering the tasks, you will be able to invoke them from the CLI:

```bash
zrb hello-py
zrb hello-cmd
zrb hello
```


</details>

### The Output

<div align="center">
  <img src="_images/emoji/printer.png"/>
  <p>
    <sub>
      System.out.print("Brrrr");
    </sub>
  </p>
</div>

Try to run `zrb hello` and see how Zrb executes `hello_cmd` and `hello_py` along the way.

```bash
zrb hello
```

```
User name [Tom]: Jerry
🤖 ○ ◷ 2023-12-14 20:48:05.852 ❁  45423 → 1/3 🍋        zrb hello-cmd • Run script: echo "Hello, Jerry. Current mode: DEV"
🤖 ○ ◷ 2023-12-14 20:48:05.853 ❁  45423 → 1/3 🍋        zrb hello-cmd • Working directory: /home/gofrendi/playground/getting-started
🤖 ○ ◷ 2023-12-14 20:48:05.859 ❁  45423 → 1/3 🐨         zrb hello-py • Hello, Jerry. Current mode: DEV
🤖 ○ ◷ 2023-12-14 20:48:05.862 ❁  45444 → 1/3 🍋        zrb hello-cmd • Hello, Jerry. Current mode: DEV
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-12-14 20:48:05.902 ❁  45423 → 1/3 🐱            zrb hello • Completed in 0.05356645584106445 seconds
To run again: zrb hello --user-name "Jerry"
```

Furthermore, you can try to set `MODE` environment in your terminal and see how it affects the output:

```bash
export MODE=PROD
zrb hello
```

Now you will see `Current mode: PROD` instead of `Current mode: DEV`.

### Advance Example: Long Running Task

<div align="center">
  <img src="_images/emoji/railway_car.png"/>
  <p>
    <sub>
      <a href="https://www.youtube.com/watch?v=vYh-PjASgNk" target="blank">It's a long, long journey</a>
    </sub>
  </p>
</div>


Let's start with a use case:

- We want to serve a single HTML file
- The HTML file contains some information from environment variables and user inputs.
- Zrb should generate the HTML file based on a single HTML template.
- Whenever the HTML template is modified, Zrb should re-generate the HTML file.

We can break down the requirements into some tasks.

```
     🥬                               🍳
Prepare .env ─────────┐ ┌────────► Build HTML ──────┐
                      │ │                           │       🥗
                      ├─┤                           ├────► Serve
                      │ │                           │
Prepare HTML ─────────┘ └───► Monitor and Rebuild ──┘
  Template                            HTML
    🥬                                🔍 
```

Let's see how we build this:

```python
from typing import Any
from zrb import (
    runner, Parallel, Task, CmdTask, python_task, ResourceMaker, RecurringTask,
    PathWatcher, TimeWatcher, HTTPChecker, Env, EnvFile, IntInput
)
import os

CURRENT_DIR = os.path.dirname(__file__)


@python_task(
    icon='🍆',
    name='prepare-template',
)
def prepare_template(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    template_dir = os.path.join(CURRENT_DIR, 'template')
    template_html_file = os.path.join(template_dir, 'index.html')
    if os.path.isfile(template_html_file):
        task.print_out(f'{template_html_file} already exists')
        return
    os.makedirs(template_dir, exist_ok=True)
    with open(template_html_file, 'w') as file:
        task.print_out(f'Creating {template_html_file}')
        file.write('\n'.join([
            '<title>ConfigTitle</title>',
            '<p>Message: ConfigMessage</p>',
            '<p>Author: ConfigAuthor</p>',
            '<p>Last Generated: LastGenerated</p>'
        ]))


@python_task(
    icon='🥬',
    name='prepare-env',
)
def prepare_env(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    env_file = os.path.join(CURRENT_DIR, '.env')
    if os.path.isfile(env_file):
        task.print_out(f'{env_file} already exists')
        return
    with open(env_file, 'w') as file:
        task.print_out(f'Creating {env_file}')
        file.write('\n'.join([
            'TITLE=My-page',
            'DEV_TITLE=My-page-dev',
            'AUTHOR=No-one'
        ]))


build = ResourceMaker(
    icon='🍳',
    name='build',
    envs=[
        Env(name='MESSAGE', default='Salve Mane')
    ],
    env_files=[
        EnvFile(path=os.path.join(CURRENT_DIR, '.env'))
    ],
    template_path=os.path.join(CURRENT_DIR, 'template'),
    destination_path=os.path.join(CURRENT_DIR, 'web'),
    replacements={
        'ConfigTitle': '{{ env.TITLE }}',
        'ConfigMessage': '{{ env.MESSAGE }}',
        'ConfigAuthor': '{{ env.AUTHOR }}',
        'LastGenerated': '{{ datetime.datetime.now() }}'
    }
)


monitor = RecurringTask(
    icon='🔍',
    name='monitor',
    task=build,
    triggers=[
        PathWatcher(path=os.path.join(CURRENT_DIR, 'template', '*.*')),
        PathWatcher(path=os.path.join(CURRENT_DIR, '.env')),
        TimeWatcher(schedule='* * * * *')
    ]
)

serve = CmdTask(
    icon='🥗',
    name='serve',
    envs=[
        Env('BIND_ADDRESS', default='0.0.0.0')
    ],
    inputs=[
        IntInput(name='port', default='8080')
    ],
    cwd=os.path.join(CURRENT_DIR, 'web'),
    cmd='python -m http.server {{ input.port }} --bind {{ env.BIND_ADDRESS }}',
    checkers=[
        HTTPChecker(host='{{ env.BIND_ADDRESS }}', port='{{ input.port }}')
    ]
)

Parallel(prepare_env, prepare_template) >> Parallel(build, monitor) >> serve
runner.register(build, monitor, serve)

```

Let's break down the task.

- `prepare-template`: This task makes the HTML template if not exists.
- `prepare-env`: This task makes an `.env` if not exists.
- `build`: This task create the HTML based on the template. It also load `.env` generated by `prepare-env`. While copying the HTML template into `web` directory, this task will also perform several replacement:
  - `ConfigTitle`: This text will be replaced with `TITLE` environment value.
  - `ConfigMessage`: This text will be replaced with `MESSAGE` environment value.
  - `ConfigAuthor`: This text will be replaced with `AUTHOR` environment value.
  - `LastGenerated`: This text will be replaced with current time (i.e., `datetime.datetime.now()`)
- `monitor`: This task will run `build` based on several triggers:
  - If there is any changes in `.env`
  - If there is any changes under `template` directory
  - Every minute
- `serve`: This task serve the HTML. Zrb will check whether this task is `Completed` or not by using a `HTTPChecker`.

We also define task dependencies and make some tasks (i.e., `build`, `monitor`, and `serve`) are available from the CLI


You can try to run the task by invoking the following command:

```bash
zrb serve
```

The html page will be available from [http://localhost:8080](http://localhost:8080).

Furthermore, you can set `ZRB_ENV` into `DEV` and see how Zrb automatically cascade `DEV_TITLE` into `TITLE`

```bash
export ZRB_ENV=DEV
zrb serve
```

Once you do so, you will see that Zrb is now showing `My-page-dev` instead of `My-page` as the page title.


🔖 [Table of Contents](README.md)