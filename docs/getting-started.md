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
- [Creating a Project](#creating-a-project)
- [Creating a Task](#creating-a-task)
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

If you already have your own Python Ecosystem (i.e., [Pyenv](https://github.com/pyenv/pyenv), [Conda](https://docs.conda.io/en/latest), or Venv), you can install Zrb using the Pip command.

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
      <a href="https://www.youtube.com/watch?v=2wVPyo_hnWw" target="_blank">Run! run! run!</a>
    </sub>
  </p>
</div>

Zrb comes with some built-in task definitions. To run a Zrb task, you need to follow the following pattern:

```bash
zrb [task-groups...] <task-name> [task-inputs...]
```

Let's see the following example:

```bash
zrb base64 encode --text "non-credential-string"
      │      │    └──────────────┬─────────────┘                            
      │      │                   │ 
      ▼      │                   ▼
  task-group │            task-input
             │
             ▼
         task-name
```

In the example, you have just run the `encode` Task under `base64` Group. You also provide `non-credential-string` as `base64`'s `text` Input.

If you don't provide the Input directly, Zrb will activate an interactive mode to let you fill in the missing values.

```bash
# Running base64 encode in an interactive mode
zrb base64 encode
Text []:
```

You can skip the interactive mode by setting `ZRB_SHOW_PROMPT` to `0` or `false` as described in [configuration section](./configurations.md). When you disable the interactive mode, Zrb will use Task Input's default value.

```bash
# Running base64 encode in a non-interactive mode.
ZRB_SHOW_PROMPT=false zrb base64 encode
```

## Task Output

As with any other CLI commands, Zrb uses `stdout` and `stderr`.

- `Standard Output (stdout)`: Usually contains the output of the program.
- `Standard Error (stderr)`: Usually contains logs, error messages, and other information.

If not specified, `stdout` and `stderr` usually refer to your default output device (i.e., screen/monitor).

Let's see an example.

```bash
zrb base64 encode --text "non-credential-string"
```

```
        ┌─ Support zrb growth and development!
        │  ☕ Donate at: https://stalchmst.com/donation
stderr  │  🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
        │  🐤 Follow us at: https://twitter.com/zarubastalchmst 
        └─ 🤖 ○ ◷ 2023-11-10 09:08:33.183 ❁ 35276 → 1/1 🍎    zrb base64 encode • Completed in 0.051436424255371094 seconds
        ┌─
stdout  |  bm9uLWNyZWRlbnRpYWwtc3RyaW5n
        └─ 
        ┌─
stderr  |  To run again: zrb base64 encode --text "non-credential-string"
        └─ 
```

Knowing `stdout` and `stderr` in detail is crucial if you want to [integrate Zrb with other tools](tutorials/integration-with-other-tools.md).

> __⚠️ WARNING:__ Base64 is a encoding algorithm that allows you to transform any characters into an alphabet which consists of Latin letters, digits, plus, and slash.
>
> Anyone can easily decode a base64-encoded string. __Never use it to encrypt your password or any important credentials!__

## Task Group

Referring to our previous example, we can see that the `encode` Task is located under `base64` Group. This grouping mechanism makes Zrb Tasks more organized and discoverable. You can think of Groups as directories/folders.

```
zrb
├── base64            # group
│   ├── decode        # task (zrb base64 decode)
│   └── encode        # task (zrb base64 encode)
├── devtool           # group
│   └── install       # sub-group
│       ├── aws       # task (zrb devtool install aws)
│       ├── docker    # task (zrb devtool install docker)
│       ├── gcloud    # task (zrb devtool install gcloud)
│       ├── ...
│       └── zsh       # task (zrb devtool install zsh)
├── ...
└── watch-changes     # task (zrb watch-changes)
```

When you type `zrb` in your terminal, you will see top-level Tasks and Groups. You can then type the Sub-Group/Task name until you find what you need.

Let's try it.

```bash
# Showing top level Tasks and Groups.
zrb

# Showing any Groups or Tasks under `base64` group
zrb base64

# Running `encode` Task under `base64` group
zrb base64 encode
```

That's all you need to know to run Zrb Tasks.

In the rest of this section, you will learn about Zrb Projects and how to make your own Zrb Tasks.

# Creating A Project

<div align="center">
  <img src="_images/emoji/building_construction.png"/>
  <p>
    <sub>
      A project is like a fridge light; it only works when you open it to check.
    </sub>
  </p>
</div>

At its basic, a Project is a directory containing a single file named `zrb_init.py`. This simple setup is already sufficient for a simple hello-world project.

Zrb automatically imports `zrb_init.py` and loads any registered Tasks. Those Tasks will be available and discoverable from the Zrb CLI command.

To create a simple Project, you can invoke the following command:

```bash
mkdir my-project
cd my-project
touch zrb_init.py
```

For a more sophisticated way to create a Project, you should run `zrb project create`. Please visit [the project section](concepts/project.md) for more information.

# Creating A Task

<div align="center">
  <img src="_images/emoji/clipboard.png"/>
  <p>
    <sub>
      Finishing a task: 10% skill, 90% not getting distracted by the internet.
    </sub>
  </p>
</div>

Zrb Task is the smallest unit of your automation.

Zrb has multiple Task Types, including `CmdTask`, `python_task`, `DockerComposeTask`, `FlowTask`, `Server`, `RemoteCmdTask`, `RsyncTask`, `ResourceMaker`, etc.

All Tasks are defined and written in Python. Typically, a Zrb Task has multiple parameters:

- Common Configuration.
  - `inputs`: interfaces to read user input at the beginning of the execution.
  - `envs`: interfaces to read and use OS Environment Variables.
  - `env_files`: interfaces to read and use Environment Files.
  - `group`: Where the Task belongs to, if unspecified, Zrb will put the Task directly under the top-level command.
- Dependency configuration.
  - `upstreams`: Upstreams (dependencies) of the current Task. You can also use `shift-right` (`>>`) operator to define the dependencies.
- Lifecycle related parameters.
  - `retry`: How many retries should be attempted.
  - `retry_interval`: How long to wait before the next retry attempt.
  - `fallbacks`: What to do if the Task is failed and no retry attempt will be performed.
  - `checkers`: How to determine if a Task is `Ready`.
  - `checking_interval`: How long to wait before checking for Task's readiness.
  - `run`: What a Task should do.
  - `on_triggered`: What to do when a Task is `Triggered`.
  - `on_waiting`: What to do when a Task is `Waiting`.
  - `on_skipped`: What to do when a Task is `Skipped`.
  - `on_started`: What to do when a Task is `Started`.
  - `on_ready`: What to do when a Task is `Ready`.
  - `on_retry`: What to do when a Task is `Retry`.
  - `on_failed`: What to do when a Task is `Failed`.
  - `should_execute`: Whether a Task should be `Started` or not (`Skipped`).

Every Task has its life-cycle state:
- `Triggered`: The Task is triggered.
- `Waiting`: The Task is waiting for all it's upstreams to be ready.
- `Skipped`: The Task is not executed and will immediately enter the `Ready` state.
- `Started`: The Task execution is started.
- `Failed`: The Task execution is failed. It will enter the `Retry` state if the current attempt is less than the maximum attempt.
- `Retry`: The task will be restarted.
- `Ready`: The task is ready.

To learn more about Task, please visit [the concept section](concepts/README.md).

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

- __Using Task Class__ (e.g., `CmdTask`, `DockerComposeTask`, `FlowTask`, `Server`, `RemoteCmdTask`, `RsyncTask`, `ResourceMaker`, etc)
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
- __RsyncTask__: Copy file from/to remote computers using `rsync` command.
- __ResourceMaker__: Create resources (source code/documents) based on provided templates.
- __FlowTask__: Combine unrelated tasks into a single Workflow.
- __Server__: Handle recurring tasks.


### Using `@python_task` decorator

`@python_task` decorator is a syntactic sugar for `Task` class. You can use the decorator as follows:

```python
@python_task(
    name='task-name,
    # other_task_property=some_value,
    # ...
)
def task_name(*args, **kwargs):
    pass
```

`@python_task` decorator turns your function into a `Task`. That means `task_name` is now a Zrb Task and you can no longer treat `task_name` as a function (i.e., `task_name()` won't work).

## Common Task Parameters

<div align="center">
  <img src="_images/emoji/house.png"/>
  <p>
    <sub>
      Property buying: where Monopoly meets your real bank balance.
    </sub>
  </p>
</div>

The following properties are usually available:

- __name__: The name of the Task. When you invoke the task using the CLI, you need to use this name. You should wrote Task name in `kebab-case` (i.e., separated by `-`).
- __description__: The description of the task.
- __group__: The task group to which the task belongs.
- __inputs__: Task inputs and their default values.
- __envs__: Task's environment variables.
- __env_files__: Task's environment files.
- __retry__: How many times to retry the execution before entering `Failed` state.
- __upstreams__: Upstreams of the task. You can provide `AnyTask` as upstream.
- __checkers__: List of checker tasks. You need this for long-running tasks.
- __runner__: Only available in `@python_task`. The valid value is `zrb.runner`.


# Basic Example

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

## Import Statement

<div align="center">
  <img src="_images/emoji/truck.png"/>
  <p>
    <sub>
      <a href="https://xkcd.com/353/" target="_blank">import antigravity.</a>
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

## `hello-cmd` Definition

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

## `hello-py` Definition

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

## `hello` Definition And Its Dependencies


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

## Register Tasks to The `runner`

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

## The Output

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

# Advance Example: Long Running Task

<div align="center">
  <img src="_images/emoji/railway_car.png"/>
  <p>
    <sub>
      <a href="https://www.youtube.com/watch?v=vYh-PjASgNk" target="_blank">It's a long, long journey</a>
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
    runner, Parallel, Task, CmdTask, python_task, ResourceMaker, Server,
    Controller, PathWatcher, TimeWatcher, HTTPChecker, Env, EnvFile, IntInput
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


monitor = Server(
    icon='🔍',
    name='monitor',
    controllers=[
      Controller(
        name="build-periodically",
        action=build,
        triggers=[
            PathWatcher(path=os.path.join(CURRENT_DIR, 'template', '*.*')),
            PathWatcher(path=os.path.join(CURRENT_DIR, '.env')),
            TimeWatcher(schedule='* * * * *')
        ]
      )
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
- `serve`: This task serves the HTML. Zrb will check whether this task is `Completed` by using a `HTTPChecker`.

We also define task dependencies and make some tasks (i.e., `build`, `monitor`, and `serve`) available from the CLI


You can try to run the task by invoking the following command:

```bash
zrb serve
```

The HTML page will be available from [http://localhost:8080](http://localhost:8080).

Furthermore, you can set `ZRB_ENV` into `DEV` and see how Zrb automatically cascade `DEV_TITLE` into `TITLE`

```bash
export ZRB_ENV=DEV
zrb serve
```

Once you do so, you will see that Zrb now shows `My-page-dev` instead of `My-page` as the page title. You can learn more about environment cascading at the [environment section](concepts/environments.md).


# Next

Now you are ready. You can proceed with the [concept section](concepts/README.md) to learn more about the details.

Have fun, Happy Coding, and Automate More!!!


🔖 [Table of Contents](README.md)
