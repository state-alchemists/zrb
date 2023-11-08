🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Copy and Re-use Task

Rather than define similar task twice, you can copy existing task into a new one and applying necessary changes.

```python
from zrb import runner, CmdTask, StrInput, Env

# Define hello task
hello: CmdTask = CmdTask(
    name='hello',
    inputs=[StrInput(name='name', description='Name', default='world')],
    envs=[Env(name='GREETINGS', os_name='', default='Hello')],
    cmd='echo {{env.GREETINGS}} {{input.name}}'
)

# Copy hello task
local_hello = hello.copy()

# Update name, input, and env
local_hello.set_name('hello-local')
local_hello.add_input(
    StrInput(name='name', description='Name', default='dunia')
)
local_hello.add_env(
    Env(name='GREETINGS', os_name='', default='Halo')
)

runner.register(hello)
runner.register(local_hello)
```

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)