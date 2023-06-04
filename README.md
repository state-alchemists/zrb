# Zrb: Your Faithful Companion

![](https://raw.githubusercontent.com/state-alchemists/zrb/main/images/zrb/android-chrome-192x192.png)

Zrb is a CLI-based task runner and low-code platform. Once installed, you can automate day-to-day tasks, generate projects and applications, and even deploy your applications to Kubernetes with a few commands.

To use Zrb, you need to be familiar with CLI.
# Installation

Installing Zrb is as easy as typing the following command in your terminal:

```bash
pip install zrb
```

If the command doesn't work, you probably don't have Pip/Python on your computer. See `Main prerequisites` to install them.

# Main prerequisites

Since Zrb is written in Python, you need to install a few things before installing Zrb:

- `Python`
- `Pip`
- `Venv`

If you are using Ubuntu, the following command should work:

```bash
sudo apt-get install python3 python3-pip python3-venv python-is-python3
```

If you are using Mac, the following command might work:

```bash
# Make sure you have homebrew installed, see: https://brew.sh/
brew install python3
ln -s venv/bin/pip3 /usr/local/bin/pip
ln -s venv/bin/python3 /usr/local/bin/python
```

# Other prerequisites

If you want to generate applications using Zrb and run them on your computer, you will also need:

- `Node.Js` and `Npm`. 
    - You need Node.Js to modify/transpile frontend code into static files.
    - You can visit [Node.Js website](https://nodejs.org/en) for installation instructions.
- `Docker` and `Docker-compose` plugin.
    - You need `Docker` and `Docker-compose` plugin to
        - Run `Docker-compose` based tasks
        - Run some application prerequisites like RabbitMQ, Postgre, or Redpanda. 
    - The easiest way to install `Docker`, `Docker-compose` plugin, and local `Kubernetes` is by using [Docker Desktop](https://www.docker.com/products/docker-desktop/).
    - You can also install `Docker` and `Docker-compose` plugin by following [Docker installation guide](docker-compose).
-  `Kubernetes` cluster.
    - Zrb allows you to deploy your applications into `Kubernetes`.
    - To test it locally, you will need a [minikube](https://minikube.sigs.k8s.io/docs/) or other alternatives. However, the easiest way is by enabling `Kubernetes` on your `Docker Desktop`.

# Getting started

To get started, you can create a project as follow:

```bash
zrb project create --project-dir=my-project
```

A project is a directory containing `zrb_init.py` and other resources.

Once you create a project, you can start defining tasks. To understand why we need to define tasks, plese visit [tasks documentation](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/task.md).

Zrb supports the following tasks:

- [Python task](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/python-task.md)
- [Cmd task](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/cmd-task.md)
- [Docker-Compose task](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/docker-compose-task.md)
- [Checkers](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/checker.md)
    - [HTTP checker](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/http-checker.md)
    - [Port checker](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/port-checker.md)
    - [Path checker](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/path-checker.md)
- [Resource maker](https://github.com/state-alchemists/zrb/blob/main/docs/concepts/resource-maker.md)

You can also add an application to your project and start/deploy it as a monnolithic or microservices:

```bash
# Create a project
zrb project create --project-dir my-project --project-name "My Project"
cd my-project

# Create a Fastapp
zrb project add fastapp --project-dir . --app-name "fastapp" --http-port 3000

# Add library module to fastapp
zrb project add fastapp-module --project-dir . --app-name "fastapp" --module-name "library"

# Add entity named "books"
zrb project add fastapp-crud --project-dir . --app-name "fastapp" --module-name "library" \
    --entity-name "book" --plural-entity-name "books" --column-name "code"

# Add column to the entity
zrb project add fastapp-field --project-dir . --app-name "fastapp" --module-name "library" \
    --entity-name "book" --column-name "title" --column-type "str"

# Run Fastapp
zrb project start-fastapp

# Run Fastapp as container
zrb project start-fastapp-container

# Deploy fastapp
zrb project deploy-fastapp
```
# Autoloaded tasks

Zrb will automatically load the following task definitions:

- Every task definition in `ZRB_INIT_SCRIPTS`.
    - You can use a colon separator (`:`) to define multiple scripts in `ZRB_INIT_SCRIPTS`. For example:
        ```bash
        ZRB_INIT_SCRIPTS=~/personal/zrb_init.py:~/work/zrb_init.py
        ```
- Every task definition in `zrb_init.py` in your current directory.
    - If Zrb cannot find any in your current directory, it will look at the parent directories until it finds one.
- Every built-in task definition given `ZRB_SHOULD_LOAD_BUILTIN` equals `1` or unset.

# How to run tasks programmatically

To run a task programmatically, you need to create a `main loop`.

For example:

```python
from zrb import CmdTask

cmd_task = CmdTask(
    name='sample',
    cmd='echo hello'
)
main_loop = cmd_task.create_main_loop(env_prefix='')
result = main_loop() # This run the task
print(result.output) # Should be "hello"
```

# Enable shell completion

To enable shell completion, you need to set `_ZRB_COMPLETE` variable.

For `bash`:

```bash
eval $(_ZRB_COMPLETE=bash_source zrb)
```

For `zsh`:

```bash
eval $(_ZRB_COMPLETE=zsh_source zrb)
```

Once set, you will have a shell completion in your session:

```bash
zrb <TAB>
zrb md5 hash -<TAB>
```

Visit [click shell completion](https://click.palletsprojects.com/en/8.1.x/shell-completion/) for more information.

# Configuration

The following configurations are available:

- `ZRB_HOME_DIR`: Zrb home directory.
    - Default: Zrb home directory
- `ZRB_LOGGING_LEVEL`: Logging verbosity.
    - Default: `WARNING`
    - Possible values:
        - `CRITICAL`
        - `ERROR`
        - `WARNING`
        - `WARN` (The same as `WARNING`)
        - `INFO`
        - `DEBUG`
        - `NOTSET`
- `ZRB_INIT_SCRIPTS`: List of task registration script that should be loaded by default.
    - Default: Empty
    - Possible values: List of script paths, separated by colons(`:`).
    - Example: `~/personal/zrb_init.py:~/work/zrb_init.py`
- `ZRB_ENV`: Environment prefix that will be used when loading Operating System's environment.
    - Default: Empty
    - Possible values: Any combination of alpha-numeric and underscore
    - Example: `DEV`
- `ZRB_SHOULD_LOAD_BUILTIN`: Whether load builtin tasks or not
    - Default: `1`
    - Possible values:
        - `1`
        - `0`
- `ZRB_SHELL`: Default shell for running cmdTask
    - Default: `bash`
    - Possible value:
        - `/usr/bin/bash`
        - `/usr/bin/sh` 
- `ZRB_SHOW_ADVERTISEMENT`: Whether show advertisement or not.
    - Default: `1`
    - Possible value:
        - `1`
        - `0`
- `ZRB_SHOW_PROMPT`: Whether show prompt or not.
    - Default: `1`
    - Possible value:
        - `1`
        - `0`

# Quirks

- No one is sure how to pronounce Zrb. Let's keep it that way.
- If not set, `PYTHONUNBUFFERED` will be set to `1`.
- Once `zrb_init.py` is loaded, Zrb will automatically:
    - Set `ZRB_PROJECT_DIR` to `zrb_init.py`'s parent directory.
    - If loaded as CLI, Zrb will also:
        - Adding `ZRB_PROJECT_DIR` to `PYTHONPATH`.
- Zrb passes several keyword arguments that will be accessible from the task's run method:
    - `_args`: Shell argument when the task is invoked.
    - `_task`: Reference to the current task.
- You can access the built-in command groups by importing `zrb.builtin_group`.
- How environments are loaded:
    - `env_files` has the lowest priority, it will be overridden by `env`
    - `env` will override each other, the last one takes greater priority
    - If you define a `DockerComposeTask`, it will automatically fill your environment with the ones you use in your docker-compose file. The environment defined that way will have a very low priority. They will be overridden by both `env_files` and `env`.

# For contributors

There is a toolkit you can use to test whether Zrb is working as intended.

To use the toolkit, you can invoke the following command:

```bash
source ./project.sh
```

Once you load the toolkit, you can start playing around.

```bash
# Run test and serve coverage.
zrb test

# Test zrb in playground
zrb prepare-playground
```


# For maintainers

To publish Zrb, you need a `Pypi` account:

- Log in or register to [https://pypi.org/](https://pypi.org/)
- Create an API token

You can also create a `TestPypi` account:

- Log in or register to [https://test.pypi.org/](https://test.pypi.org/)
- Create an API token

Once you have your API token, you need to create a `~/.pypirc` file:

```
[distutils]
index-servers =
   pypi
   testpypi

[pypi]
  repository = https://upload.pypi.org/legacy/
  username = __token__
  password = pypi-xxx-xxx
[testpypi]
  repository = https://test.pypi.org/legacy/
  username = __token__
  password = pypi-xxx-xxx
```

To publish Zrb, you can do the following:

```bash
source ./project.sh

# Publish Zrb to TestPypi
zrb publish-test

# Publish Zrb to Pypi
zrb publish
```
