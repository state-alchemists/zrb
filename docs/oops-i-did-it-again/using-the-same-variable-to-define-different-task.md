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

You can see that `prepare-python-project` and `prepare-node-project` are assigned to the same variable.

Using that variable as upstream or checker will lead to a tricky situation. In our case, we want to perform `pip install` before starting Fast API. But since we re-assign the variable to `prepare-node-project`, we will got `npm install` instead.

# Avoiding the Problem

Beware of your variable name. Give your variable the same name as your task name.


🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)
