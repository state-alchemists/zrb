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

- `zrb.py` in your current directory.
- or any Python file defined in `ZRB_SCRIPTS` environment.

You can use a colon separator (`:`) to define multiple scripts in `ZRB_SCRIPTS`. For example:

```bash
ZRB_SCRIPTS=~/personal/zrb.py:~/work/zrb.py
```

Your Zrb script should contain your tak definitions. For example:

```python
from zrb import runner

install_venv = CmdTask(
    name='install-venv',
    inputs=[
        StrInput(name='dir', default='venv', prompt='Venv directory'),
        BooleanInput(
            name='installrequirements', 
            default=True, 
            prompt='Install requirements (y/n)'
        )
    ],
    command='''
        pip -m venv {{ input.dir }}
        source {{ input.dir}}/bin/activate
        {% if input.installrequirements %}pip install -r requirements.txt{% endif %}
    '''
)

run_fastapi = CmdProcess(
    name='run-fastapi',
    directory='./fastapi',
    envs=[
        Env(name='PORT', global_name='FASTAPI_PORT', default='3000')
    ],
    inputs=[
        BooleanInput(name='reload', default=False, prompt='Auto reload (y/n)')
    ],
    upstream=[install_venv],
    command='uvicorn main:app {% if input.reload %}--reload{% endif %}',
    check=[
        HttpPortCheck('{{env.PORT}}'),
    ]
)

runner.register(install_venv)
runner.register(run_fastapi)
```

Once you register your tasks, they will be accessible from the terminal:

```bash
# Invoke `run-fastapi` and make sure `install-venv` has been already performed
export FASTAPI_PORT=8080
zrb run-fastapi -reload=yes -installrequirements=yes
```

# For developer

There is a toolkit to help you manage zrb

```
source ./toolkit.sh
```
