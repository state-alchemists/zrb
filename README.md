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
from zrb import runner

install_venv = CmdTask(
    name='install_venv',
    inputs=[
        StrInput(name='dir', default='venv', prompt='Venv directory'),
        BooleanInput(
            name='installrequirements', 
            default=True, 
            prompt='Install requirements (y/n)'
        )
    ],
    cmd='''
        pip -m venv {{ input.dir }}
        source {{ input.dir }}/bin/activate
        {% if input.installrequirements %}pip install -r requirements.txt{% endif %}
    '''
)

run_fastapi = CmdProcess(
    name='run_fastapi',
    directory='./fastapi',
    envs=[
        Env(name='PORT', os_name='FASTAPI_PORT', default='3000')
    ],
    inputs=[
        BooleanInput(name='reload', default=False, prompt='Auto reload (y/n)')
    ],
    upstreams=[install_venv],
    cmd='uvicorn main:app {% if input.reload %}--reload{% endif %}',
    check=[
        HttpPortCheck(port='{{env.PORT}}'),
    ]
)

runner.register(install_venv)
runner.register(run_fastapi)
```

Once you register your tasks, they will be accessible from the terminal:

```bash
# Invoke `run-fastapi` and make sure `install-venv` has been already performed
export FASTAPI_PORT=8080
zrb run_fastapi -reload=yes -installrequirements=yes
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
