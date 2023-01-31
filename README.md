# Zrb (WIP)

Your faithful sidekick

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

- `zrb_init.py` in your current directory.
- or any Python file defined in `ZRB_INIT_SCRIPTS` environment.

You can use a colon separator (`:`) to define multiple scripts in `ZRB_INIT_SCRIPTS`. For example:

```bash
ZRB_SCRIPTS=~/personal/zrb_init.py:~/work/zrb_init.py
```

Your Zrb script should contain your task definitions. For example:

```python
from zrb import (
    Group, CmdTask, Env, HTTPChecker, StrInput, runner
)

# zrb hello
hello = CmdTask(
    name='hello',
    inputs=[
        StrInput(name='name', shortcut='n', default='world', prompt='Name')
    ],
    cmd='echo Hello {{input.name}}'
)
runner.register(hello)

make = Group(name='make', description='Make things')

# zrb make coffee
make_coffee = CmdTask(
    name='coffee',
    group=make,
    upstreams=[hello],
    cmd='echo Coffee for you ☕'
)
runner.register(make_coffee)

# zrb make beer
make_beer = CmdTask(
    name='beer',
    group=make,
    upstreams=[hello],
    cmd='echo Cheers 🍺'
)
runner.register(make_beer)

make_gitignore = Group(
    name='gitignore', description='Make gitignore', parent=make
)

# zrb make gitignore python
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

# zrb make gitignore nodejs
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

# zrb server run
run_server = CmdTask(
    name='run',
    group=server,
    upstreams=[make_coffee, make_beer],
    inputs=[
        StrInput(name='dir', shortcut='d', default='.', prompt='Directory')
    ],
    envs=[
        Env(name='PORT', os_name='WEB_PORT', default='3000')
    ],
    cmd='python -m http.server $PORT --directory {{input.dir}}',
    checkers=[
        HTTPChecker(port='{{env.PORT}}')
    ]
)
runner.register(run_server)
```

Once registered, your task will be accessible from the terminal:

```bash
export WEB_PORT=8080
zrb server run
```

The output will be similar to this:

```
Name [world]: Go Frendi
Directory [.]:
🤖 ➜ 2023-01-31T08:35:59.559413 ⚙ 8229 ➤ 1 of 3 | 🦁 hello Hello Go Frendi
🤖 ➜ 2023-01-31T08:35:59.864599 ⚙ 8231 ➤ 1 of 3 | 🐭 coffee Coffee for you ☕
🤖 ➜ 2023-01-31T08:35:59.864710 ⚙ 8233 ➤ 1 of 3 | 🦁 beer Cheers 🍺
🤖 ➜ 2023-01-31T08:43:50.228739 ⚙ 9112 ➤ 1 of 3 | 🐮 run Serving HTTP on 0.0.0.0 port 8080 (http://0.0.0.0:8080/) ...
🤖 ➜ 2023-01-31T08:36:00.461907 ⚙ 8228 ➤ 1 of 3 | 🐭 http_checker HEAD http://localhost:8000/ 200 (OK)
🤖 🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉
🤖 run completed in
🤖 0.9103696346282959 seconds
🤖 🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉

🤖 ⚠ 2023-01-31T08:43:50.494470 ⚙ 9112 ➤ 1 of 3 | 🐮 run 127.0.0.1 - - [31/Jan/2023 08:43:50] "HEAD / HTTP/1.1" 200 -
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
- `ZRB_LOAD_DEFAULT`: Whether load default tasks or not
    - Default: `1`
    - Possible values:
        - `1`
        - `0`

# For contributors

There is a toolkit you can use to test whether Zrb is working as intended.

To use the toolkit, you can invoke the following:

```bash
source ./toolkit.sh

# Build Zrb
build-zrb

# Test zrb in playground
prepare-playground
cd playground
source venv/bin/activate
# Start testing/creating use cases...
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
