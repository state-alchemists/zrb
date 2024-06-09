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
- [Defining Dependencies](#defining-dependencies)
- [Advanced Example](#advanced-example-long-running-task)

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

Zrb comes with some built-in Tasks. To run a Zrb Task, you need to follow the following pattern:

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

Every Zrb Task has its life-cycle state:
- `Triggered`: The Task is triggered (either by the user or by the other Task).
- `Waiting`: Zrb has already triggered the Task. The Task is now waiting for all its upstreams to be ready.
- `Skipped`: Task upstreams are ready, but the Task is not executed and will immediately enter the `Ready` state.
- `Started`: The upstreams are ready, and Zrb is now starting the Task execution.
- `Failed`: Zrb failed to execute the Task. It will enter the `Retry` state if the current attempt does not exceed the maximum attempt.
- `Retry`: The task has already entered the `Failed` state. Now, Zrb will try to start the Task execution.
- `Ready`: The task is ready.

You can learn more about the lifecycle states in [the task lifecycle documentation](concepts/task-lifecycle.md).

Zrb has multiple Task Types, including `CmdTask`, `DockerComposeTask`, `RemoteCmdTask`, `RsyncTask`, `ResourceMaker`, `FlowTask`, `Server`, etc.

All Tasks are defined and written in Python and should be accessible from your Project's `zrb_init.py`. Typically, a Zrb Task has multiple parameters:

- Common parameters.
  - `name`: Task name, conventionally written in `kebab-case` (i.e., separated by `-`). It acts as an identifier when users execute the Task from the CLI.
  - `inputs`: interfaces to read user input at the beginning of the execution.
  - `envs`: interfaces to read and use OS Environment Variables.
  - `env_files`: interfaces to read and use Environment Files.
  - `group`: Where the Task belongs to, if unspecified, Zrb will put the Task directly under the top-level command.
- Dependency parameters.
  - `upstreams`: Upstreams (dependencies) of the current Task. You can also use the `shift-right` (`>>`) operator to define the dependencies.
- Lifecycle related parameters.
  - `retry`: Maximum retry attempt.
  - `retry_interval`: The duration is to wait before Zrb starts the next attempt.
  - `fallbacks`: Action to take if the Task has failed for good.
  - `checkers`: How to determine if a Task is `Ready`.
  - `checking_interval`: The duration to wait before Zrb checks for the Task's readiness.
  - `run`: Action to do when Zrb executes the Task.
  - `on_triggered`: Action to do when a Task is `Triggered`.
  - `on_waiting`: Action to do when a Task is `Waiting`.
  - `on_skipped`: Action to do when a Task is `Skipped`.
  - `on_started`: Action to do when a Task is `Started`.
  - `on_ready`: Action to do when a Task is `Ready`.
  - `on_retry`: Action to do when a Task is `Retry`.
  - `on_failed`: Action to do when a Task is `Failed`.
  - `should_execute`: Condition to determine whether a Task should be `Started` or `Skipped`.

There are two ways to define a Task:

- By creating an instance of a `TaskType` (e.g., `CmdTask`, `DockerComposeTask`, `RemoteCmdTask`, `RsyncTask`, `ResourceMaker`, `FlowTask`, `Server`)
- By using `@python_task` decorator

We will explore them in more detail. In the next two subsections, we will create a `hello` Task using `CmdTask` and `@python_task` decorator. The Tasks should read and use the `USER` environment variable and read `color` from user input.

## Creating Instances of TaskTypes

```python
from zrb import CmdTask, Env, StrInput, runner

hello_cmd = CmdTask(
    name="hello-cmd",
    envs=[Env(name="USER", default="guest")],
    inputs=[
      StrInput(name="color", prompt="Your favorite color", default="black")
    ],
    cmds=[
        'echo "Hello $USER"',
        'echo "Your favorite color is {{input.color}}"',
    ]
)
runner.register(hello_cmd)
```

In the example, we create an instance of a `CmdTask` and assign it to the `hello_cmd` variable. Finally, we register the Task in Zrb's `runner` to make it accessible from the CLI. The Task has several properties.

- `name`: Representing the Task name, conventionally written in `kebab-case` (i.e., separated by `-`). In our example, the Task name was `hello-cmd`
- `envs`: Representing the environment variable used by the Task.
- `inputs`: Representing user inputs used by the Task.
- `cmd`: Representing the command line to execute.

Notice how we use `$USER` to get the value of the Environment Variable and `{{input.color}}` to get the user input.

Once you declare and register the Task in your `zrb_init.py`, you can run the Task by invoking the command.

```bash
zrb hello-cmd
```

## Using `@python_task` Decorator

```python
from zrb import Env, StrInput, python_task, runner

@python_task(
    name="hello-py",
    envs=[Env(name="USER", default="guest")],
    inputs=[
      StrInput(name="color", prompt="Your favorite color", default="black")
    ],
)
def hello_py(*args, **kwargs):
    task = kwargs.get("_task")
    # get environment variable: user
    env_map = task.get_env_map()
    user = env_map.get("USER")
    # get color
    color = kwargs.get("color")
    greetings = "\n".join([
        f"Hello {user}",
        f"Your favorite color is {color}",
    ])
    return greetings
runner.register(hello_py)
```

In the example, we use a `@python_task` decorator to transform the `hello_py` function into a Task. Finally, we register the Task in Zrb's `runner` to make it accessible from the CLI.

Note that `hello_py` is now a Task, not a function. So, calling `hello_py()` won't work.

As in the previous section, the `hello_py` Task has several properties.

- `name`: Representing the Task name, conventionally written in `kebab-case` (i.e., separated by `-`). In our example, the Task name was `hello-py`.
- `envs`: Representing the environment variable used by the Task.
- `inputs`: Representing user inputs used by the Task.


When Zrb executes the Task, it will pass all user inputs as keyword arguments. Additionally, Zrb adds `_task` argument so you can use it to get the environment map.

> __⚠️ WARNING:__ When using the `@python_decorator`, you must fetch the environment map using  `kwargs.get("_task").get_env_map()`, instead of `os.getenv()`.. Unlike `os.getenv()`, the `get_env_map()` method handles Task environment rendering and other internal mechanism.


Once you declare and register the Task in your `zrb_init.py`, you can run the Task by invoking the command.

```bash
zrb hello
```

# Defining Dependencies

You can already see how we define Tasks using `CmdTask` and `@python_task` decorator. Now, let's see how you can define Task dependencies.

You can define dependencies using the Task's `upstreams` or the shift-right operator.

In the following example, we want to create a Task named `hello` that depends on `hello-cmd` and `hello-py`.

```
hello-py ───┐
            ├─► hello
hello-cmd ──┘
```


```python
from zrb import CmdTask, Env, Parallel, StrInput, python_task, runner

hello_cmd = CmdTask(
    name="hello-cmd",
    envs=[Env(name="USER", default="guest")],
    inputs=[
      StrInput(name="color", prompt="Your favorite color", default="black")
    ],
    cmds=[
        'echo "Hello $USER"',
        'echo "Your favorite color is {{input.color}}"',
    ]
)


@python_task(
    name="hello-py",
    envs=[Env(name="USER", default="guest")],
    inputs=[
      StrInput(name="color", prompt="Your favorite color", default="black")
    ],
)
def hello_py(*args, **kwargs):
    task = kwargs.get("_task")
    # get environment variable: user
    env_map = task.get_env_map()
    user = env_map.get("USER")
    # get color
    color = kwargs.get("color")
    greetings = "\n".join([
        f"Hello {user}",
        f"Your favorite color is {color}",
    ])
    task.print_out(greetings) # make this shown as stderr
    return greetings


# Define hello along with it's dependencies
hello = Task(name='hello')
Parallel(hello_cmd, hello_py) >> hello

# Alternatively, you can use upstreams parameter:
# hello = Task(name='hello', upstreams=[hello_cmd, hello_py])

# Register tasks to runner
runner.register(hello, hello_cmd, hello_py)
```

As you register `hello`, `hello-cmd`, and `hello-py` to the runner, you can call them from the CLI.

```bash
zrb hello
zrb hello-cmd
zrb hello-py
```

Notice that when you run `zrb hello`, Zrb automatically executes `hello-cmd` and `hello-py` first since `hello` depends on them.

# Advanced Example: Long Running Task

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
            name="build-on-template-change",
            # action=CmdTask(name="abc"),
            action=build,
            trigger=PathWatcher(path=os.path.join(CURRENT_DIR, 'template', '*.*')),
        ),
        Controller(
            name="build-on-env-change",
            # action=CmdTask(name="abc"),
            action=build,
            trigger=PathWatcher(path=os.path.join(CURRENT_DIR, '.env')),
        ),
        Controller(
            name="build-periodically",
            # action=CmdTask(name="abc"),
            action=build,
            trigger=TimeWatcher(schedule='* * * * *')
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
