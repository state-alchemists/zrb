🔖 [Table of Contents](README.md)

# Getting started

Zrb is an automation tool. With Zrb you can run tasks using command-line-interface.

There are project tasks and common tasks. Project tasks are usually bind to a project, while common tasks can be executed from anywhere.

# Running a task

You can run any Zrb task by invoking the following pattern:

```bash
zrb [task-groups] <task-name> [task-parameters]
```

For example, you want to run `encode` that is located under `base64` group, you can do so by execute the following command:

```bash
zrb base64 encode --text "non-credential-string"
```

```
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/pull requests at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ➜  2023-06-11T05:09:06.283002 ⚙ 3549 ➤ 1 of 1 • 🍋    zrb base64 encode • zrb base64 encode completed in 0.11719107627868652 seconds
To run again: zrb base64 encode --text "non-credential-string"
bm9uLWNyZWRlbnRpYWwtc3RyaW5n
```

Related tasks are usually located under the same group. For example, you have `decode` task under `base64` group as well.

```bash
zrb base64 decode --text "bm9uLWNyZWRlbnRpYWwtc3RyaW5n"
```

# Getting available tasks/task groups

To see all available task/task groups, you can type `zrb` and press enter.

```bash
zrb
```

```
Usage: zrb [OPTIONS] COMMAND [ARGS]...

  Super framework for your super app.

Options:
  --help  Show this message and exit.

Commands:
  base64            Base64 operations
  concat            concat
  devtool           Developer tools management
  env               Environment variable management
  eval              Evaluate Python expression
  md5               MD5 operations
  explain           Explain things 
  project           Project management
  ubuntu            Ubuntu related commands
  update            Update zrb
  version           Get Zrb version
```

You can keep doing this until you find the task you want to execute

```bash
zrb base64
```

```
Usage: zrb base64 [OPTIONS] COMMAND [ARGS]...

  Base64 operations

Options:
  --help  Show this message and exit.

Commands:
  decode  Decode base64 task
  encode  Encode base64 task
```

# Using prompt

Once you find your task, you can just type the task without bothering about the parameters. Zrb will automatically prompt you to fill the parameter interactively.

```bash
zrb base64 encode
```

```
Text []: non-credential-string
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/pull requests at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ➜  2023-06-11T05:27:07.824839 ⚙ 3740 ➤ 1 of 1 • 🍌    zrb base64 encode • zrb base64 encode completed in 0.11709976196289062 seconds
To run again: zrb base64 encode --text "non-credential-string"
bm9uLWNyZWRlbnRpYWwtc3RyaW5n
```

> __NOTE:__ To disable prompt, you can set `ZRB_SHOW_PROMPT` to `0` or `false`. Please refer to [configuration section](./configurations.md) for more information.

# Creating a project

To make things more manageable, you can put related task definitions and resources under the same project.

You can create a project under `my-project` directory by invoking the following command:

```bash
zrb project create --project-dir my-project
```

Once invoked, you will have a directory named `my-project`. You can move to the directory and start to see how a project looks like:

```bash
cd my-project
ls -al
```

```
total 44
drwxr-xr-x 5 gofrendi gofrendi 4096 Jun 11 05:29 .
drwxr-xr-x 4 gofrendi gofrendi 4096 Jun 11 05:29 ..
drwxr-xr-x 7 gofrendi gofrendi 4096 Jun 11 05:29 .git
-rw-r--r-- 1 gofrendi gofrendi   21 Jun 11 05:29 .gitignore
-rw-r--r-- 1 gofrendi gofrendi 1776 Jun 11 05:29 README.md
drwxr-xr-x 3 gofrendi gofrendi 4096 Jun 11 05:29 _automate
-rwxr-xr-x 1 gofrendi gofrendi 1517 Jun 11 05:29 project.sh
-rw-r--r-- 1 gofrendi gofrendi   12 Jun 11 05:29 requirements.txt
drwxr-xr-x 2 gofrendi gofrendi 4096 Jun 11 05:29 src
-rw-r--r-- 1 gofrendi gofrendi   34 Jun 11 05:29 template.env
-rw-r--r-- 1 gofrendi gofrendi   54 Jun 11 05:29 zrb_init.py
```

Every Zrb project contains a file named `zrb_init.py`. This file is your entry point to define all tasks/configurations.

It is recommended that you define your tasks under `_automate` directory and import them into your `zrb_init.py`. This will help you manage the [separation of concerns](https://en.wikipedia.org/wiki/Separation_of_concerns).

Aside from `zrb_init.py`, you will also find some other files/directory:

- `.git` and `.gitignore`, indicating that your project is also a git repository.
- `README.md`, your README file.
- `project.sh`, a shell script to initiate your project.
- `requirements.txt`, list of necessary python packages to run start a project. Make sure to update this if you declare a task that depends on other Python library.
- `template.env`, your default environment variables.
- `_automate`, a directory contains task definitions that should be imported in `zrb_init.py`.
- `src`, your project resources (e.g., source code, docker compose file, helm charts, etc)

By default, Zrb will create a default `task-group` named `project`. Try to type:

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

# Creating a simple task

Once your project has been created, you can add some new tasks to your project.

Let's say you work for a company named `Arasaka`, and you want to show a cool CLI banner for your company.

```bash
zrb project add cmd-task --project-dir . --task-name show-banner
```

Zrb will automatically do a few things for you:

- Create `_automate/show_banner.py`
- Import `_automate.show_banner` into `zrb_init.py`.

Now you can try to run the task:

```bash
zrb project show-banner
```

```
🤖 ➜  2023-06-11T05:52:27.267892 ⚙ 4388 ➤ 1 of 3 • 🍓 zrb project show-banner • Run script: echo show banner
🤖 ➜  2023-06-11T05:52:27.268193 ⚙ 4388 ➤ 1 of 3 • 🍓 zrb project show-banner • Current working directory: /home/gofrendi/zrb/playground/my-project
🤖 ➜  2023-06-11T05:52:27.272726 ⚙ 4389 ➤ 1 of 3 • 🍓 zrb project show-banner • show banner
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/pull requests at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ➜  2023-06-11T05:52:27.318296 ⚙ 4389 ➤ 1 of 3 • 🍓 zrb project show-banner • zrb project show-banner completed in 0.11460638046264648 seconds
To run again: zrb project show-banner
show banner
```

Now let's make the banner cooler with `figlet`. You can do so by editing `_automate/show_banner.py`. If you are using VSCode, you can type `code .` in your terminal.

> ⚠️ We will use `figlet`. Try to type `figlet hello` and see whether things work or not. If you are using Ubuntu, you might need to install figlet by invoking `sudo apt install figlet`.

Make sure to modify the `cmd` property of your `show_banner` task, so that it looks like the following:

```python
from zrb import CmdTask, runner
from zrb.builtin._group import project_group

###############################################################################
# Task Definitions
###############################################################################

show_banner = CmdTask(
    name='show-banner',
    description='show banner',
    group=project_group,
    cmd=[
        'figlet Arasaka'
    ]
)
runner.register(show_banner)

```

Cool. You make it. [Saburo Arasaka](https://cyberpunk.fandom.com/wiki/Saburo_Arasaka) will be proud of you 😉.

# Creating a long-running task

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
from zrb import CmdTask, runner, IntInput, PortChecker
from zrb.builtin._group import project_group
from _automate.show_banner import show_banner
import os

###############################################################################
# Task Definitions
###############################################################################

notebook_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'src', 'notebooks'
)

start_jupyterlab = CmdTask(
    name='start-jupyterlab',
    description='start jupyterlab',
    group=project_group,
    inputs=[
        IntInput(name='jupyterlab-port', default=8080)
    ],
    upstreams=[show_banner],
    cmd='jupyter lab --no-browser --port={{input.jupyterlab_port}} ' +
        f'--notebook-dir="{notebook_path}"',
    checkers=[
        PortChecker(port='{{input.jupyterlab_port}}')
    ]
)
runner.register(start_jupyterlab)

```

First of all, we import `IntInput` and `PortChecker`, so that we can ask the user to choose the port number and check whether jupyterlab has been started on that port.

We also need to import `os`, so that we can determine the location of your `notebook_path`.

Finally we add some properties to `start_jupyterlab`:

- `inputs`: List of user inputs. We add a new input named `jupyterlab-port`. By default, the value will be `8080`.
- `upstreams`: List of tasks that should be completed before the current task is started. We want `show_banner` to be executed here.
- `cmd`: Command to be executed. You can use Jinja templating here. `{{input.jupyterlab_port}}` refers to the value `jupyterlab-port` input.
- `checkers`: List of task to determine whether current task has been completed or not. In this case we want to make sure that the port has already available for requests.

## Starting the jupyterlab

Finally, let's see and make sure things are working:

```
Jupyterlab port [8080]:
🤖 ➜  2023-06-11T06:45:42.731189 ⚙ 6237 ➤ 1 of 3 • 🐨 zrb project show-banner • Run script: figlet Arasaka
🤖 ➜  2023-06-11T06:45:42.731499 ⚙ 6237 ➤ 1 of 3 • 🐨 zrb project show-banner • Current working directory: /home/gofrendi/zrb/playground/my-project
🤖 ➜  2023-06-11T06:45:42.736205 ⚙ 6238 ➤ 1 of 3 • 🐨 zrb project show-banner •     _                        _
🤖 ➜  2023-06-11T06:45:42.736518 ⚙ 6238 ➤ 1 of 3 • 🐨 zrb project show-banner •    / \   _ __ __ _ ___  __ _| | ____ _
🤖 ➜  2023-06-11T06:45:42.736782 ⚙ 6238 ➤ 1 of 3 • 🐨 zrb project show-banner •   / _ \ | '__/ _` / __|/ _` | |/ / _` |
🤖 ➜  2023-06-11T06:45:42.737349 ⚙ 6238 ➤ 1 of 3 • 🐨 zrb project show-banner •  / ___ \| | | (_| \__ \ (_| |   < (_| |
🤖 ➜  2023-06-11T06:45:42.737637 ⚙ 6238 ➤ 1 of 3 • 🐨 zrb project show-banner • /_/   \_\_|  \__,_|___/\__,_|_|\_\__,_|
🤖 ➜  2023-06-11T06:45:42.737940 ⚙ 6238 ➤ 1 of 3 • 🐨 zrb project show-banner •
🤖 ➜  2023-06-11T06:45:42.741398 ⚙ 6237 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • Run script: jupyter lab --no-browser --port=8080 --notebook-dir="/home/gofrendi/zrb/playground/my-project/src/notebooks"
🤖 ➜  2023-06-11T06:45:42.741681 ⚙ 6237 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • Current working directory: /home/gofrendi/zrb/playground/my-project
🤖 ⚠  2023-06-11T06:45:43.347664 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.347 ServerApp] Package jupyterlab took 0.0000s to import
🤖 ⚠  2023-06-11T06:45:43.354037 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.353 ServerApp] Package jupyter_lsp took 0.0061s to import
🤖 ⚠  2023-06-11T06:45:43.354341 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [W 2023-06-11 06:45:43.353 ServerApp] A `_jupyter_server_extension_points` function was not found in jupyter_lsp. Instead, a `_jupyter_server_extension_paths` function was found and will be used for now. This function name will be deprecated in future releases of Jupyter Server.
🤖 ⚠  2023-06-11T06:45:43.357141 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.356 ServerApp] Package jupyter_server_terminals took 0.0029s to import
🤖 ⚠  2023-06-11T06:45:43.357496 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.357 ServerApp] Package notebook_shim took 0.0000s to import
🤖 ⚠  2023-06-11T06:45:43.357800 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [W 2023-06-11 06:45:43.357 ServerApp] A `_jupyter_server_extension_points` function was not found in notebook_shim. Instead, a `_jupyter_server_extension_paths` function was found and will be used for now. This function name will be deprecated in future releases of Jupyter Server.
🤖 ⚠  2023-06-11T06:45:43.358139 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.357 ServerApp] jupyter_lsp | extension was successfully linked.
🤖 ⚠  2023-06-11T06:45:43.360703 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.360 ServerApp] jupyter_server_terminals | extension was successfully linked.
🤖 ⚠  2023-06-11T06:45:43.364479 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.364 ServerApp] jupyterlab | extension was successfully linked.
🤖 ⚠  2023-06-11T06:45:43.489074 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.488 ServerApp] notebook_shim | extension was successfully linked.
🤖 ⚠  2023-06-11T06:45:43.538464 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.537 ServerApp] notebook_shim | extension was successfully loaded.
🤖 ⚠  2023-06-11T06:45:43.539844 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.539 ServerApp] jupyter_lsp | extension was successfully loaded.
🤖 ⚠  2023-06-11T06:45:43.540686 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.540 ServerApp] jupyter_server_terminals | extension was successfully loaded.
🤖 ⚠  2023-06-11T06:45:43.541056 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.540 LabApp] JupyterLab extension loaded from /home/gofrendi/zrb/venv/lib/python3.9/site-packages/jupyterlab
🤖 ⚠  2023-06-11T06:45:43.541399 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.540 LabApp] JupyterLab application directory is /home/gofrendi/zrb/venv/share/jupyter/lab
🤖 ⚠  2023-06-11T06:45:43.541722 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.541 LabApp] Extension Manager is 'pypi'.
🤖 ⚠  2023-06-11T06:45:43.543932 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.543 ServerApp] jupyterlab | extension was successfully loaded.
🤖 ⚠  2023-06-11T06:45:43.544397 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.543 ServerApp] Serving notebooks from local directory: /home/gofrendi/zrb/playground/my-project/src/notebooks
🤖 ⚠  2023-06-11T06:45:43.544742 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.544 ServerApp] Jupyter Server 2.6.0 is running at:
🤖 ⚠  2023-06-11T06:45:43.545059 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.544 ServerApp] http://localhost:8080/lab?token=74085eb7b8304271e028c5e0e01237ebaadbb13a54a64921
🤖 ⚠  2023-06-11T06:45:43.545395 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.544 ServerApp]     http://127.0.0.1:8080/lab?token=74085eb7b8304271e028c5e0e01237ebaadbb13a54a64921
🤖 ⚠  2023-06-11T06:45:43.545720 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [I 2023-06-11 06:45:43.544 ServerApp] Use Control-C to stop this server and shut down all kernels (twice to skip confirmation).
🤖 ⚠  2023-06-11T06:45:43.547067 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • [C 2023-06-11 06:45:43.546 ServerApp]
🤖 ⚠  2023-06-11T06:45:43.547407 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab •
🤖 ⚠  2023-06-11T06:45:43.547855 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab •     To access the server, open this file in a browser:
🤖 ⚠  2023-06-11T06:45:43.548628 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab •         file:///home/gofrendi/.local/share/jupyter/runtime/jpserver-6240-open.html
🤖 ⚠  2023-06-11T06:45:43.549002 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab •     Or copy and paste one of these URLs:
🤖 ⚠  2023-06-11T06:45:43.549389 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab •         http://localhost:8080/lab?token=74085eb7b8304271e028c5e0e01237ebaadbb13a54a64921
🤖 ⚠  2023-06-11T06:45:43.549734 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab •         http://127.0.0.1:8080/lab?token=74085eb7b8304271e028c5e0e01237ebaadbb13a54a64921
🤖 ➜  2023-06-11T06:45:43.641677 ⚙ 6237 ➤ 1 of 1 • 🍐           port-check • Checking localhost:8080 (OK)
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/pull requests at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ➜  2023-06-11T06:45:43.643523 ⚙ 6240 ➤ 1 of 3 • 🐶 zrb project start-jupyterlab • zrb project start-jupyterlab completed in 1.103727102279663 seconds
To run again: zrb project start-jupyterlab --jupyterlab-port "8080"
```

Open up your browser on `http://localhost:8080` and start working.

# Now you are ready

We have cover the minimum basics to work ~~for Arasaka~~ with Zrb.

To learn more about tasks and other concepts, you can visit [Zrb concept section](concepts/README.md).

Also, do you know that you can make and deploy a CRUD application without even touching your IDE/text editor? Check out [our tutorials](tutorials/README.md) for more cool tricks.


🔖 [Table of Contents](README.md)