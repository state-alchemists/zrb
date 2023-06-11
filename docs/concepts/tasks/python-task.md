🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# Python task

Python task is very powerful to do complex logic.

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

```bash
zrb say-hello --name=John
```

You can also use `async` function if you think you need to.

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
