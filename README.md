# Zrb (WIP)

Your faithful companion.

# How to install

```bash
pip install zrb
```

# How to use

To run a task, you can invoke the following command:

```bash
zrb <task> [arguments]
```

# How to define tasks

Zrb will automatically load:

- `zrb_init.py` in your current directory (or parent directories).
- or any Python file defined in `ZRB_INIT_SCRIPTS` environment.

You can use a colon separator (`:`) to define multiple scripts in `ZRB_INIT_SCRIPTS`. For example:

```bash
ZRB_SCRIPTS=~/personal/zrb_init.py:~/work/zrb_init.py
```

Your Zrb script (e.g: `./zrb_init.py`) should contain your task definitions. For example:

```python
from typing import Any
from zrb import (
    runner, Env, StrInput, Group, Task, CmdTask, HTTPChecker
)

'''
Simple Python task, concatenate words
'''
concat = Task(
    name='concat',
    inputs=[StrInput(name='separator', description='Separator', default=' ')],
)
runner.register(concat)


# set concat's runner
@concat.runner
def run(*args: str, **kwargs: Any) -> str:
    separator = kwargs.get('separator', ' ')
    return separator.join(args)


'''
Simple CLI task, read input and show output
'''
hello = CmdTask(
    name='hello',
    inputs=[StrInput(name='name', description='Name', default='world')],
    cmd='echo Hello {{input.name}}'
)
runner.register(hello)

make = Group(name='make', description='Make things')

'''
Simple CLI task, part of 'make' group
'''
make_coffee = CmdTask(
    name='coffee',
    group=make,
    upstreams=[hello],
    cmd='echo Coffee for you ☕'
)
runner.register(make_coffee)

'''
Simple CLI task, part of 'make' group
'''
make_beer = CmdTask(
    name='beer',
    group=make,
    upstreams=[hello],
    cmd='echo Cheers 🍺'
)
runner.register(make_beer)

'''
Sub group of 'make'
'''
make_gitignore = Group(
    name='gitignore', description='Make gitignore', parent=make
)

'''
Simple CLI task, part of 'make_gitignore' group.
Having multiline cmd
'''
make_gitignore_python = CmdTask(
    name='node',
    group=make_gitignore,
    cmd=[
        'echo "node_modules/" >> .gitignore'
        'echo ".npm" >> .gitignore'
        'echo "npm-debug.log" >> .gitignore'
    ]
)
runner.register(make_gitignore_python)

'''
Simple CLI task, part of 'make_gitignore' group.
Having multiline cmd
'''
make_gitignore_nodejs = CmdTask(
    name='node',
    group=make_gitignore,
    cmd=[
        'echo "__pycache__/" >> .gitignore'
        'echo "venv" >> .gitignore'
    ]
)
runner.register(make_gitignore_nodejs)

server = Group(
    name='server', description='Server related commands'
)

'''
Long running CLI task.
Run a server and waiting for the port to be ready.
'''
run_server = CmdTask(
    name='run',
    group=server,
    upstreams=[make_coffee, make_beer],
    inputs=[StrInput(name='dir', description='Directory', default='.')],
    envs=[Env(name='PORT', os_name='WEB_PORT', default='3000')],
    cmd='python -m http.server $PORT --directory {{input.dir}}',
    checkers=[HTTPChecker(port='{{env.PORT}}')]
)
runner.register(run_server)
```

Once registered, your task will be accessible from the terminal.

For example, you can run a server by performing:

```bash
export WEB_PORT=8080
zrb server run
```

The output will be similar to this:

```
Name [world]: Go Frendi
Dir [.]:
🤖 ➜ 2023-02-02T07:17:35.384284 ⚙ 6095 ➤ 1 of 3 • 🍊         hello • Hello Go Frendi
🤖 ➜ 2023-02-02T07:17:35.491491 ⚙ 6097 ➤ 1 of 3 • 🐷   make coffee • Coffee for you ☕
🤖 ➜ 2023-02-02T07:17:35.492019 ⚙ 6099 ➤ 1 of 3 • 🦁     make beer • Cheers 🍺
🤖 ➜ 2023-02-02T07:17:35.618819 ⚙ 6101 ➤ 1 of 3 • 🍒    server run • Serving HTTP on 0.0.0.0 port 3000 (http://0.0.0.0:3000/) ...
🤖 ➜ 2023-02-02T07:17:35.684434 ⚙ 6094 ➤ 1 of 1 • 🍇    http_check • HEAD http://localhost:3000/ 200 (OK)
🤖 🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉
🤖 🍒 server run completed in
🤖 🍒 0.31129932403564453 seconds
🤖 🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉

🤖 ⚠ 2023-02-02T07:17:35.685651 ⚙ 6101 ➤ 1 of 3 • 🍒    server run • 127.0.0.1 - - [02/Feb/2023 07:17:35] "HEAD / HTTP/1.1" 200 -
```

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


# Configuration

The following configurations are available:

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
- `ZRB_SHOULD_LOAD_DEFAULT`: Whether load default tasks or not
    - Default: `1`
    - Possible values:
        - `1`
        - `0`
- `ZRB_SHELL`: Default shell for running cmdTask
    - Default: empty, indicating the system's default (usually `/usr/bin/bash` or `/usr/bin/sh`)
    - Possible value:
        - `/usr/bin/bash`
        - `/usr/bin/sh` 
        - `node`
        - `python`

# Quirks

- Zrb name is as is, no one is sure how to pronounce it.
- Once `zrb_init.py` is loaded, Zrb will automatically set `ZRB_PROJECT_DIR` to `zrb_init.py`'s parent directory.
Zrb passes several keyword arguments that will be accessible from the task's run method:
    - `_args`: Shell argument when the task is invoked.
    - `_task`: Reference to the current task.

# For contributors

There is a toolkit you can use to test whether Zrb is working as intended.

To use the toolkit, you can invoke the following:

```bash
source ./toolkit.sh

# Build Zrb
build-zrb

# Run test and show coverage.
# You can access the coverage report by visiting http://localhost:9000
# You can also change the port by setting __TEST_COVERAGE_PORT variable
test-zrb

# Test zrb in playground
prepare-playground
play
# Start testing/creating use cases...
zrb server run
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
source ./toolkit.sh

# Build Zrb
build-zrb

# Publish Zrb to TestPypi
test-publish-zrb

# Publish Zrb to Pypi
publish-zrb
```
