🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)

# Not Registering A Task to A Runner

```python
from zrb import CmdTask, runner

hello = CmdTask(
    name='hello',
    cmd='echo "hello world"'
)
```

```bash
zrb hello
# task not found
```

If you want your task to be available through the CLI, you need to register it to Zrb's runner.

> __📝 NOTE:__ A task that is not registered to Zrb's runner will not be available through the CLI, but can still be used as upstreams/checkers.

# Avoiding the Problem

Don't forget to register your task to Zrb's runner

```python
from zrb import CmdTask, runner

hello = CmdTask(
    name='hello',
    cmd='echo "hello world"'
)
runner.register(hello)
```

If you are using `@python_task` decorator, you can use `runner` property as follow:

```python
from typing import Any
from zrb import python_task, runner

@python_task(
    name='hello',
    runner=runner
)
def hello(*args: Any, **kwargs: Any):
    task = kwargs.get('_task')
    task.print_out('hello world')
```


🔖 [Table of Contents](../README.md) / [Oops, I Did It Again](README.md)