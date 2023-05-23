# Zrb (WIP): Your Faithful Companion

![](https://raw.githubusercontent.com/state-alchemists/zrb/master/images/zrb/android-chrome-192x192.png)

Zrb is a task runner to help you automate day-to-day tasks.
# Installation

```bash
pip install zrb
```

# Create a project

A project is a directory containing a Python file named `zrb_init.py`.

The recommended way to create a Zrb project is by using Zrb built-in generator. To create a Zrb project using the built-in generator, you can invoke the following command:

```bash
zrb project create --project-dir=my-project
```

To start working on the project, you can invoke the following command:

```bash
source project.sh
```

The command will make you a Python virtual environment, as well as install necessary Python packages.

## Create a very minimal project

Aside from the built-in generator, you can also make a project manually by invoking the following command:

```bash
mkdir my-project
cd my-project
touch zrb_init.py
```

This might be useful for demo/experimentation.

# Define tasks

Zrb comes with many types of tasks:

- Python task
- Cmd task
- Docker compose task
- Http checker
- Port Checker
- Path Checker
- Resource maker

Every task has its inputs, environments, and upstreams. By defining the upstreams, you can make several tasks run in parallel. Let's see the following example:

```
install-pip --------------------------------------> run-server
                                             |
install-node-modules  ---> build-frontend ----
```

```python
# File location: zrb_init.py
from zrb import CmdTask, HttpChecker, EnvFile, runner

# Install pip package for requirements.txt in src directory
install_pip_packages = CmdTask(
    name='install-pip',
    cmd='pip install -r requirements.txt',
    cwd='src'
)

# Install node modules in src/frontend directory
install_node_modules = CmdTask(
    name='install-node-modules',
    cmd='npm install --save-dev',
    cwd='src/frontend'
)

# Build src/frontend
# To build the frontend, you need to make sure that node_modules has already been installed.
build_frontend = CmdTask(
    name='build-frontend',
    cmd='npm run build',
    cwd='src/frontend',
    upstreams=[install_node_modules]
)

# Start the server.
# In order to start the server, you need to make sure that:
# - Necessary pip packages has been already installed
# - Frontend has already been built
# By default it should use environment defined in `src/template.env`.
# You can set the port using environment variable WEB_PORT
# This WEB_PORT environment will be translated into PORT variable internally
# You can use the port to check whether a server is ready or not.
run_server = CmdTask(
    name='run-server',
    envs=[
        Env(name='PORT', os_name='WEB_PORT', default='3000')
    ],
    env_files=[
        EnvFile(env_file='src/template.env', prefix='WEB')
    ]
    cmd='python main.py',
    cwd='src',
    upstreams=[
        install_pip_packages,
        build_frontend
    ],
    checkers=[HTTPChecker(port='{{env.PORT}}')],
)
runner.register(run_server)
```

Once defined, you can start the server by invoking the following command:

```bash
zrb run-server
```

Zrb will make sure that the tasks are executed in order based on their upstreams.
You will also see that `install-pip-packages` and `install-node-modules` are executed in parallel since they are independent of each other.

# Define a Python task

Defining a Python task is simple.

```python
from zrb import python_task, Env, StrInput, runner

@python_task(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='PYTHONUNBUFFERED', default=1)
    ],
    runner=runner
)
def say_hello(*args, **kwargs) -> str:
    name = kwargs.get('name')
    greetings = f'Hello, {name}'
    task = kwargs.get('_task')
    task.print_out(greetings)
    return greetings
```

You can then run the task by invoking:

```
zrb say-hello --name=John
```

Python task is very powerful to do complex logic. You can also use `async` function if you think you need to.

# Define a Cmd task

You can define a Cmd task by using `CmdTask` class.

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd='echo {{input.name}}'
)
runner.register(say_hello)
```

If you need a multi-line command, you can also define the command as a list:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd=[
        'echo {{input.name}}',
        'echo Yeay!!!'
    ]
)
runner.register(say_hello)
```

However, if your command is too long, you can also load it from other file:


```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd_path='hello_script.sh'
)
runner.register(say_hello)
```


You can then run the task by invoking:

```
zrb say-hello --name=John
```


# Define a Docker Compose task

Docker Compose is a convenient way to run containers on your local computer.

Suppose you have the following Docker Compose file:

```yaml
# docker-compose.yml file
version: '3'

services:
  # The load balancer
  nginx:
    image: nginx:1.16.0-alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "${HOST_PORT:-8080}:80"
```

You can define a task to run your Docker Compose file (i.e., `docker compose up`) like this:

```python
from zrb import DockerComposeTask, HTTPChecker, Env, runner

run_container = DockerComposeTask(
    name='run-container',
    compose_cmd='up',
    compose_file='docker-compose.yml',
    envs=[
        Env(name='HOST_PORT', default='3000')
    ],
    checkers=[
        HTTPChecker(
            name='check-readiness', port='{{env.HOST_PORT}}'
        )
    ]
)
runner.register(run_container)
```

# Define checkers

Some tasks might run forever, and you need a way to make sure whether those tasks are ready or not.

Let's say you invoke `npm run build:watch`. This command will build your Node.js App into `dist` directory, as well as watch the changes and rebuild your app as soon as there are some changes.

- You need to start the server after the app has been built for the first time.
- You can do this by checking whether the `dist` folder already exists or not.
- You can use `PathChecker` for this purpose

Let's see how to do this:

```python
from zrb import CmdTask, PathChecker, Env, EnvFile, runner

build_frontend = CmdTask(
    name='build-frontend',
    cmd='npm run build',
    cwd='src/frontend',
    checkers=[
        PathChecker(path='src/frontend/dist')
    ]
)

run_server = CmdTask(
    name='run-server',
    envs=[
        Env(name='PORT', os_name='WEB_PORT', default='3000')
    ],
    env_files=[
        EnvFile(env_file='src/template.env', prefix='WEB')
    ]
    cmd='python main.py',
    cwd='src',
    upstreams=[
        build_frontend
    ],
    checkers=[HTTPChecker(port='{{env.PORT}}')],
)
runner.register(run_server)
```

Aside from `PathChecker`, Zrb also has `HTTPChecker` and `PortChecker`.

# Define a resource maker

ResourceMaker is used to generate resources. Let's say you have a `template` folder containing a file named `app_name.py`:

```python
# file: template/app_name.py
message = 'Hello world_name'
print(message)
```

You can define a ResourceMaker like this:

```python
from zrb import ResourceMaker, StrInput, runner

create_hello_world = ResourceMaker(
    name='create-hello-world',
    inputs=[
        StrInput('app-name'),
        StrInput('world-name'),
    ],
    replacements={
        'app_name': '{{input.app_name}}',
        'world_name': '{{input.world_name}}',
    },
    template_path='template',
    destination_path='.',
)
runner.register(create_hello_world)
```

Now when you invoke the task, you will get a new file as expected:

```bash
zrb create-hello-world --app-name=wow --world-name=kalimdor
echo ./wow.py
```

The result will be:

```python
# file: template/wow.py
message = 'Hello kalimdor'
print(message)
```

This is a very powerful building block to build anything based on the template.

# Using Zrb to build an application (WIP)

You can use Zrb to build a powerful application with a few commands:

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

You should notice that every module in `fastapp` can be deployed/treated as microservices.

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
