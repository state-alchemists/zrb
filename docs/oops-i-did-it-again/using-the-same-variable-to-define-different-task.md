🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)

# Using The Same Variable to Define Different Task

```python
from zrb import runner, CmdTask

prepare = CmdTask(
    name='prepare-python-project',
    cmd='pip install -R requirements.txt'
)
runner.register(prepare)

prepare = CmdTask(
    name='prepare-node-project',
    cmd='npm install'
)
runner.register(prepare)

run_fastapi = CmdTask(
    name='run-fastapi',
    cmd='uvicon main:app'
    upstreams=[
        prepare, # <-- Here is the problem, `npm install`` or `pip install`? 
    ]
)
runner.register(run_fastapi)
```

🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)
