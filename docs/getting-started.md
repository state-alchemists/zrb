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
- [Ultimate Example: Personal CI/CD](#ultimate-example-personal-cicd)

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

> __📝 NOTE:__  Zrb comes with builtin Task Definitions. Unless you set `ZRB_SHOULD_LOAD_BUILTIN` to `false`, Zrb will automatically loads the builtin Tasks.

That's all you need to know to run Zrb Tasks.

In the rest of this page, you will learn about Zrb Projects and how to make your own Zrb Tasks.

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

Zrb has multiple Task Types, including `CmdTask`, `DockerComposeTask`, `RsyncTask`, `ResourceMaker`, `FlowTask`, `Server`, etc.

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

- By creating an instance of a `TaskType` (e.g., `CmdTask`, `DockerComposeTask`, `RsyncTask`, `ResourceMaker`, `FlowTask`, `Server`)
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

# Ultimate Example: Personal CI/CD

According to [Wikipedia](https://en.wikipedia.org/wiki/CI/CD), CI/CD is the combined practice of continuous integration (CI) and continuous delivery (CD) or, less often, continuous deployment. They are sometimes referred to collectively as continuous development or continuous software development.

- Continuous integration: Frequent merging of several small changes into a main branch.
- Continuous delivery: When teams produce software in short cycles with high speed and frequency so that reliable software can be released at any time and with a simple and repeatable deployment process when deciding to deploy.
- Continuous deployment: When new software functionality is rolled out completely automatically.

In the following example, we will make a simple CI/CD pipeline that __continuously generates static pages__ and __deploys them to the remote server__ via SSH.

We won't use any Git server or CI/CD platform. Instead, we will build a custom automation using Zrb.

In our scenario, Developers can do several things manually:
- Edit `templates` and `configurations`.
- Run the `build` command to create a `deployable` based on existing `templates` and `configurations`.
- Copy `deployable` to remote servers.
- Run the `serve` command to make it accessible from the internet.

We also want to enhance the workflow so that whenever `templates` and `configurations` are __modified__, the `deployable` will be __generated__, __copied__ to the server, and __served__ to the user. 

```
       ┌────────────────────────────────────────────┐       ┌────────────────┐
       │ Local Computer                             │       │ Server         │
       │                                            │       │                │
       │   ┌─────────────┐                          │       │                │
    ┌──┼───┤Template     ├─┐                        │       │                │           ~~~~~~~~
    │  │   └─────────────┘ │           ┌──────────┐ │       │   ┌──────────┐ │           ~      ~
    │  │                   ├──Build───►│Deployable├─┼─Rsync─┼──►│Deployable├─┼─Serve───► ~ User ~
    │  │   ┌─────────────┐ │    │      └──────────┘ │   |   │   └──────────┘ │   │       ~      ~
    ├──┼───┤Configuration├─┘    │                   │   │   │                │   │       ~~~~~~~~
    │  │   └─────────────┘      │                   │   │   │                │   │
    │  │                        │                   │   │   │                │   │
    │  └────────────────────────┼───────────────────┘   │   └────────────────┘   │
    │                           │                       │                        │
 Create/                       Run                     Run                      Run
  Edit                          ────────────────────────┬─────────────────────────
    │                                                   │
    │                                              ~~~~~~~~~~~~~
    │                                              ~           ~
    └──────────────────────────────────────────────~ Developer ~
                                                   ~           ~
                                                   ~~~~~~~~~~~~~
```

## Import and Define Values

```python
from zrb import (
    AnyTask, Controller, HTTPChecker, Env, EnvFile, FlowTask, StrInput, PasswordInput,
    Parallel, PathWatcher, ResourceMaker, RemoteConfig, CmdTask, RsyncTask,
    Server, python_task, runner
)

import os

CURRENT_DIR_PATH = os.path.dirname(__file__)
TEMPLATE_DIR_PATH = os.path.join(CURRENT_DIR_PATH, "template")
OUTPUT_DIR_PATH = os.path.join(CURRENT_DIR_PATH, "output")
ENV_FILE_PATH = os.path.join(CURRENT_DIR_PATH, "config.env")

DEFAULT_ENV_MAP = {
    "TITLE": "My homepage",
    "CONTENT": "Hello world",
    "AUTHOR": "Myself",
    "WEB_HOST": "stalchmst.com",
    "WEB_PORT": "5000",
}
```

We start our quest by importing some objects we want to use later. We also define several global variables we will use when defining our tasks:

- `CURRENT_DIR_PATH`: current directory where the script is defined.
- `TEMPLATE_DIR_PATH`: directory where we will put the `template`.
- `OUTPUT_DIR_PATH`: directory where `deployable` will be generated.
- `ENV_FILE_PATH`: `configuration` file name.
- `DEFAULT_ENV_MAP`: Default `configuration` value.

## Initiate Templates and Configurations

```python
@python_task(
    name="init-template",
    should_execute=not os.path.isdir(TEMPLATE_DIR_PATH)
)
def init_template(*args, **kwargs):
    task: AnyTask = kwargs.get("_task")
    task.print_out("Creating template")
    os.makedirs(TEMPLATE_DIR_PATH)
    with open(os.path.join(TEMPLATE_DIR_PATH, "index.html"), "w") as file:
        file.write("\n".join([
            "<title>CfgTitle</title>",
            "<h1>CfgTitle</h1>",
            "<p>CfgContent</p>",
            "<p>CfgAuthor, Last Updated on CfgLastGenerated</p>"
        ]))


@python_task(
    name="init-env",
    should_execute=not os.path.isfile(ENV_FILE_PATH)
)
def init_env(*args, **kwargs):
    task: AnyTask = kwargs.get("_task")
    task.print_out("Creating configuration")
    with open(ENV_FILE_PATH, "w") as file:
        file.write("\n".join([
            f"export {key}={DEFAULT_ENV_MAP[key]}" for key in DEFAULT_ENV_MAP
        ]))
```

We then continue with some Task definitions. We need a way to ensure that our `template` and `configuration` exist in the first place.

We define the Tasks by using the `@python_task` decorator, and we only want the Tasks to be executed if the `template` or `configuration` doesn't exist. To do so, we make use of `should_execute` parameters:

- Zrb will execute `init_template` only if `TEMPLATE_DIR_PATH` directory does not exist (`not os.path.isdir(TEMPLATE_DIR_PATH)`).
- Zrb will execute `init_env` only if `ENV_FILE_PATH` file does not exist (`not os.path.isfile(ENV_FILE_PATH)`).

As for `init_template`, we want it to create an `index.html` under `TEMPLATE_DIR_PATH`. The file contains some keywords that will be replaced when we `build` the static pages.

- `CfgTitle`: The title of the page.
- `CfgContent`: The content of the page.
- `CfgAuthor`: Page author.
- `CfgLastGenerated`: Page last generated time.

Meanwhile, `init_env` should create the `ENV_FILE_PATH` file containing environment variable definitions based on `DEFAULT_ENV_MAP` value. We are using a [list comprehension](https://www.learnpython.org/en/List_Comprehensions) to construct the content of the files, and then we merge them using `join` method.

To see what each Tasks do, you can add the following lines:

```python
# Just to test, delete before you proceed with next section
runner.register(init_template, init_env)
```

Once the Tasks are registered, you can then run them using CLI:

```bash
zrb init-template
zrb init-env
```

Notice how Zrb created `template` directory and `config.env` file.

> __⚠️ WARNING:__ You can only register a Task once. Make sure to delete the Task registration part before continuing with the next section.


## Build

```python
build = ResourceMaker(
    name="build",
    env_files=[EnvFile(path=ENV_FILE_PATH)],
    envs=[
        Env(name=key, default=DEFAULT_ENV_MAP[key]) for key in DEFAULT_ENV_MAP
    ] if not os.path.isfile(ENV_FILE_PATH) else [],
    template_path=TEMPLATE_DIR_PATH,
    destination_path=OUTPUT_DIR_PATH,
    replacements={
        "CfgTitle": "{{env.TITLE}}",
        "CfgContent": "{{env.CONTENT}}",
        "CfgAuthor": "{{env.AUTHOR}}",
        "CfgLastGenerated": "{{datetime.datetime.now()}}",
    },
)
Parallel(init_template, init_env) >> build
```

We then continue to define the `build` Task. Zrb has a particular Task Type named `ResourceMaker` that creates resources based on the existing template.

`ResourceMaker` has some important parameters that distinguish it from other Task Types:

- `template_path`: location of the template.
- `destination_path`: location where the resource should be generated.
- `replacements`: map of words to be replaced when generating the resources. 

The `replacements` property might contain [Jinja Template](https://jinja.palletsprojects.com/en/3.1.x/templates/). For more comprehensive documentation about what you can use here, you should visit [Zrb template rendering documentation](./concepts/template-rendering.md). But, in short, you can use `env`, `input`, and some standard Python modules like `os` and `datetime`.

You might notice how we use `env_files` and `envs` in the `build` Task. Since `ENV_FILE_PATH` might not exist, we need to have a fallback default environment variables based on `DEFAULT_ENV_MAP`. Note that we should not load the default environment variables if `ENV_FILE_PATH` exists.

```python
build = ResourceMaker(
    name="build",
    env_files=[EnvFile(path=ENV_FILE_PATH)],
    envs=[
        Env(name=key, default=DEFAULT_ENV_MAP[key]) for key in DEFAULT_ENV_MAP
    ] if not os.path.isfile(ENV_FILE_PATH) else [],
    # other parameter definitions
)
```

Finally, we want Zrb to execute `init_template` and `init_env` first before running `build` Task. 

```python
Parallel(init_template, init_env) >> build
```

To see what `build` Tasks do, you can add the following lines:

```python
# Just to test, delete before you proceed with next section
runner.register(build)
```

Once the Task is registered, you can then run them using CLI:

```bash
zrb build
```

Notice how Zrb created an `index.html` file under `output` directory, replacing all defined keywords with proper values.

> __⚠️ WARNING:__ You can only register a Task once. Make sure to delete the Task registration part before continuing with the next section.


## Deploy

When deploying our static page, we need to do several steps:

- Build the `deployable` (already defined in our previous sections).
- Copy `deployable` to the remote server.
- Start the web service in the remote server.

We will break down the steps and combine them into a single `FlowTask`.

### Copy to Server

```python
remote_configs = [
    RemoteConfig(
        name="remote",
        host="{{input.remote_host}}",
        user="{{input.remote_user}}",
        password="{{input.remote_pass}}"
    )
]

copy_to_server = RsyncTask(
    name="copy-to-server",
    remote_configs=remote_configs,
    src="".join([os.path.join(OUTPUT_DIR_PATH), "/"]),
    dst="{{input.remote_path}}"
) 
```

Since we have already defined the `build` Task, we continue to create a `copy_to_server` task. We use `RsyncTask`, a Zrb Task Type that synchronizes files using `rsync` utility.

`RsyncTask` has some distinguished parameters:

- `remote_configs`: list of remote connection configurations.
- `src`: source path.
- `is_src_remote`: whether `src` is on the remote server or not (default: `False`)
- `dst`: destination path.
- `is_dst_remote`: whether `dst` is on the remote server or not (default: `True`)

In the example, we define the `remote_configs` to pick up values from user inputs. We will provide the inputs later.


### Start the Web Service

```python
start_server = CmdTask(
    name="start-server",
    remote_configs=remote_configs,
    cmd=[
        "set +e",
        "cd {{input.remote_path}}",
        "if curl http://{{env.WEB_HOST}}:{{env.WEB_PORT}}",
        "then",
        "  echo Server already running",
        "else",
        "  screen -dmS web_session bash -c 'cd {{input.remote_path}} && python -m http.server {{env.WEB_PORT}}'",
        "screen -ls",
        "fi",
    ],
    checkers=[
        HTTPChecker(
            host="{{env.WEB_HOST}}",
            port="{{env.WEB_PORT}}",
            env_files=[EnvFile(path=ENV_FILE_PATH)],
        )
    ]
)
```

> __📝 NOTE:__  Aside from `cmd` paramter, `CmdTask` has a `cmd_path` parameter. You can use this parameter to refer to the shell script file (e.g., `CmdTask(name="start-server", cmd_path=os.path.join(CURRENT_DIR, "start-server.sh"))`).


Next, we define a Task to run the web service. We use `CmdTask`, a Zrb Task Type capable on running the cmd scripts on the remote servers.

The Task shares the same `remote_configs` as the previous `RsyncTask` since they deal with the same remote server.

The `cmd` parameter contains a script to run a new `screen` session and execute a Python Web Server on that session if the `curl` request fails.

Finally, we define the `checkers` parameter and add an `HTTPChecker` on it. `HTTPChecker` is another Zrb Task Type that checks whether an HTTP Connection is ready.

By defining the `checkers`, we make sure that `start_server` will only considered ready if we can establish the HTTP connection.

### Combine Deployment Steps

```python
deploy = FlowTask(
    name="deploy",
    inputs=[
        StrInput(name="remote-host", prompt="Host", default="stalchmst.com"),
        StrInput(name="remote-user", prompt="User", default="root"),
        PasswordInput(name="remote-pass", prompt="Password"),
        StrInput(name="remote-path", prompt="Path", default="/var/www"),
    ],
    env_files=[EnvFile(path=ENV_FILE_PATH)],
    steps=[build, copy_to_server, start_server],
)
```

Finally, we combine `build`, `copy_to_server`, and `start_server` into a single `FlowTask`. `FlowTask` allows you to combine several unrelated Tasks into a single workflow.

`FlowTask` has a particular parameter named `steps`. You can add any Tasks to the steps, and they will run sequentially. If you need some Taks to run in parallel, you can do as follows:

```python
task_variable = FlowTask(
    name="task-name",
    steps=[
        [task1, task2], # task1 and task2 will run in parallel.
        task3, # task3 will run once task1 and task2 ready.
    ]
)
```

### Run Deployment

We have defined a `deploy` Task. To see what it does, you can add the following lines:

```python
# Just to test, delete before you proceed with next section
runner.register(deploy)
```

Before running the Task, you need to edit the configuration on `config.env`. Provide the desired `WEB_HOST` and `WEB_PORT` values.

After you set the configuration, you can then run the deployment using CLI:

```bash
zrb deploy
```

Zrb will prompt you to fill up several inputs:
- Remote host
- Remote user
- Remote password
- Remote path

Once you provide all the inputs, Zrb will deploy your application.


> __⚠️ WARNING:__ You can only register a Task once. Make sure to delete the Task registration part before continuing with the next section.


### Troubleshooting Deployment

We deal with computers constantly. Thus, we know you probably won't have things work on the first run unless you are very lucky. Here are some things to try when unsure why things don't work as expected.

<details>

<summary>We hope you are lucky, but in case you are not, click this.</summary>

- Ensure you have the `VPS` and `SSH` access. You can test this by accessing `ssh <remote-user>@<remote-host>` and enter your `<remote-password>`.
    - If you are using `Amazon EC2`, please follow [this guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/TroubleshootingInstancesConnecting.html).
    - If you are using `GCP Compute Engine`, please follow [this guide](https://cloud.google.com/compute/docs/troubleshooting/troubleshooting-ssh-errors).
    - Otherwise, follow your VPS provider's troubleshooting document.
- Ensure you set the configuration correctly, especially the `WEB_HOST` and `WEB_PORT`. If your VPS is not attached to any domain, you can use its public IP as your `WEB_HOST`.
- Ensure you enter the correct inputs when invoking the `zrb deploy` command.
- Ensure you have `screen` installed inside your VPS (try to run `screen --help` from your VPS using `ssh` connection).
- Ensure you have `python` installed inside your VPS (try to run `python --help` from your VPS using `ssh` connection).
    - Some Linux distributions use `python3` instead of `python`. If you are using Ubuntu or Debian-based OS on your VPS, you can try to run `sudo apt install python-is-python3`. 
- Ensure your VPS's inbound rule and firewall allow TCP access to your `WEB_PORT`. You need to check both the inbound rule and the VPS's firewall. Most VPS have a two-layer firewall. For example, [Vultr has Vultr Firewall and OS Firewall](https://docs.vultr.com/vultr-firewall).
    - To ensure your problem is not with the firewall, try to access your VPS using `ssh` connection and perform `python -m http.server <WEB_PORT>`
    - Once the web server is running, open another `ssh` connection and perform `curl <WEB_HOST>:<WEB_PORT>`
    - If things run smoothly, you probably have problems with your firewall setting.
        - If your VPS uses `ufw`, ensure that the `WEB_PORT` inbound rule is okay by invoking `sudo ufw status`.
            - If your `WEB_PORT` is not accessible, run `sudo ufw allow <WEB_PORT>/tcp` to enable the access.
        - Otherwise, please follow your VPS's OS-level firewall documentation.
    - If things don't run smoothly, you probably have your `WEB_HOST` setting wrong.
</details>

## Auto Deploy

```python
auto_deploy = Server(
    name="auto-deploy",
    controllers=[
        Controller(
            trigger=PathWatcher(path=os.path.join(TEMPLATE_DIR_PATH, "**/*.*")),
            action=deploy,
        ),
        Controller(
            trigger=PathWatcher(path=ENV_FILE_PATH),
            action=deploy,
        )
    ]
)
deploy >> auto_deploy
```

We have already defined the deployment Task. Now, it's time to make the deployment run automatically. Zrb has a Task Type named `Server` that perfectly matches this goal.

A `Server` has a parameter named `controllers`. Each `controller` has their `trigger` and `action`. Whenever Zrb detects that the `trigger` enter the `Ready` state, it will proceed by running the `action`.

In our example, we have two `controllers`. Both `controllers` have the same `action`, deploying the static page. However, they have different `triggers`. Any changes in `TEMPLATE_DIR_PATH` trigger the first `controller`, while any changes in `ENV_FILE_PATH` trigger the second one.

We use `PathWatcher` to detect changes on both `controllers`. `PathWatcher` is a special Task Type that watches for any changes in a particular `path` before becoming `Ready`.

Aside from `PathWatcher`, Zrb has another Task Type named `TimeWatcher` that watches for the current time and compares it to its `schedule` before becoming `Ready`. This Task Type is helpful if you want to run some actions periodically.

Lastly, we want Zrb to execute the deployment at least once. Thus, we define the `deploy` Task as `auto_deploy` upstream using the shift-right operator.


## Register Tasks

```python
runner.register(init_template, init_env, build, deploy, auto_deploy)
```

Now you have all Tasks defined and linked to each other. Finally, you can run the auto deployment by invoking the CLI command.

```bash
zrb auto-deploy
```

Zrb will ask you to complete several inputs before proceeding with the auto-deployment.

You can trigger the deployment by adding/editing/deleting any files in the `TEMPLATE_PATH` directory or modifying the `ENV_FILE_PATH` file.

The easiest way to trigger the changes without modifying the file content is by using the `touch` command.

```bash
touch config.env
```

## Put Everything Together

Great. The example covers pretty much everything you need to know.

<details>
<summary>
Here are the complete Task definitions.
</summary>

```python
from zrb import (
    AnyTask, Controller, HTTPChecker, Env, EnvFile, FlowTask, StrInput, PasswordInput,
    Parallel, PathWatcher, ResourceMaker, RemoteConfig, CmdTask, RsyncTask,
    Server, python_task, runner
)

import os

CURRENT_DIR_PATH = os.path.dirname(__file__)
TEMPLATE_DIR_PATH = os.path.join(CURRENT_DIR_PATH, "template")
OUTPUT_DIR_PATH = os.path.join(CURRENT_DIR_PATH, "output")
ENV_FILE_PATH = os.path.join(CURRENT_DIR_PATH, "config.env")

DEFAULT_ENV_MAP = {
    "TITLE": "My homepage",
    "CONTENT": "Hello world",
    "AUTHOR": "Myself",
    "WEB_HOST": "stalchmst.com",
    "WEB_PORT": "5000",
}


@python_task(
    name="init-template",
    should_execute=not os.path.isdir(TEMPLATE_DIR_PATH)
)
def init_template(*args, **kwargs):
    task: AnyTask = kwargs.get("_task")
    task.print_out("Creating template")
    os.makedirs(TEMPLATE_DIR_PATH)
    with open(os.path.join(TEMPLATE_DIR_PATH, "index.html"), "w") as file:
        file.write("\n".join([
            "<title>CfgTitle</title>",
            "<h1>CfgTitle</h1>",
            "<p>CfgContent</p>",
            "<p>CfgAuthor, Last Updated on CfgLastGenerated</p>"
        ]))


@python_task(
    name="init-env",
    should_execute=not os.path.isfile(ENV_FILE_PATH)
)
def init_env(*args, **kwargs):
    task: AnyTask = kwargs.get("_task")
    task.print_out("Creating configuration")
    with open(ENV_FILE_PATH, "w") as file:
        file.write("\n".join([
            f"export {key}={DEFAULT_ENV_MAP[key]}" for key in DEFAULT_ENV_MAP
        ]))


build = ResourceMaker(
    name="build",
    env_files=[EnvFile(path=ENV_FILE_PATH)],
    envs=[
        Env(name=key, default=DEFAULT_ENV_MAP[key]) for key in DEFAULT_ENV_MAP
    ] if not os.path.isfile(ENV_FILE_PATH) else [],
    template_path=TEMPLATE_DIR_PATH,
    destination_path=OUTPUT_DIR_PATH,
    replacements={
        "CfgTitle": "{{env.TITLE}}",
        "CfgContent": "{{env.CONTENT}}",
        "CfgAuthor": "{{env.AUTHOR}}",
        "CfgLastGenerated": "{{datetime.datetime.now()}}",
    },
)
Parallel(init_template, init_env) >> build

remote_configs = [
    RemoteConfig(
        name="remote",
        host="{{input.remote_host}}",
        user="{{input.remote_user}}",
        password="{{input.remote_pass}}"
    )
]

copy_to_server = RsyncTask(
    name="copy-to-server",
    remote_configs=remote_configs,
    src="".join([os.path.join(OUTPUT_DIR_PATH), "/"]),
    dst="{{input.remote_path}}"
) 

start_server = CmdTask(
    name="start-server",
    remote_configs=remote_configs,
    cmd=[
        "set +e",
        "cd {{input.remote_path}}",
        "if curl http://{{env.WEB_HOST}}:{{env.WEB_PORT}}",
        "then",
        "  echo Server already running",
        "else",
        "  screen -dmS web_session bash -c 'cd {{input.remote_path}} && python -m http.server {{env.WEB_PORT}}'",
        "screen -ls",
        "fi",
    ],
    checkers=[
        HTTPChecker(
            host="{{env.WEB_HOST}}",
            port="{{env.WEB_PORT}}",
            env_files=[EnvFile(path=ENV_FILE_PATH)],
        )
    ]
)

deploy = FlowTask(
    name="deploy",
    inputs=[
        StrInput(name="remote-host", prompt="Host", default="stalchmst.com"),
        StrInput(name="remote-user", prompt="User", default="root"),
        PasswordInput(name="remote-pass", prompt="Password"),
        StrInput(name="remote-path", prompt="Path", default="/var/www"),
    ],
    env_files=[EnvFile(path=ENV_FILE_PATH)],
    steps=[build, copy_to_server, start_server],
)

auto_deploy = Server(
    name="auto-deploy",
    controllers=[
        Controller(
            trigger=PathWatcher(path=os.path.join(TEMPLATE_DIR_PATH, "**/*.*")),
            action=deploy,
        ),
        Controller(
            trigger=PathWatcher(path=ENV_FILE_PATH),
            action=deploy,
        )
    ]
)
deploy >> auto_deploy

runner.register(init_template, init_env, build, deploy, auto_deploy)
```
</details>

 Put the definition on your `zrb_init.py`, and have fun.

# Next

Now you are ready. You can proceed with the [concept section](concepts/README.md) to learn more details.

Have fun, Happy Coding, and Automate More!!!


🔖 [Table of Contents](README.md)
