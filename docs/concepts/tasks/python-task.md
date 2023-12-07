🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# `Task`

You can turn any function with `args` and `kwargs` argument into a Python Task.


```python
from zrb import Task, Env, StrInput, runner


def say_hello(*args, **kwargs) -> str:
    name = kwargs.get('name')
    greetings = f'Hello, {name}'
    return greetings


say_hello_task = Task(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='PYTHONUNBUFFERED', default='1')
    ],
    run=say_hello
)
runner.register(say_hello_task)
```

In the example, you define a function named `say_hello`.

Then you make a task named and set it's `run` property to `say_hello` function. As you notice, Zrb will automatically pass task input into `kwargs` argument.

You can run the task by invoking:

```
zrb say-hello --name John
```

Thiw will give you a `Hello John`.

# Using `python_task` decorator

Aside from defining the function and the task separately, you can also use `python_task` decorator to turn your function into a task.

```python
from zrb import python_task, Env, StrInput, runner

@python_task(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='PYTHONUNBUFFERED', default='1')
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

Notice that you can now use `runner` as decorator argument so that you don't need to call `runner.register(say_hello)`.

You can then run the task by invoking:

```bash
zrb say-hello --name=John
```

You can also use `async` function if you think you need to.


# Technical Documentation

<!--start-doc-->
## `python_task`
python_task decorator helps you turn any Python function into a task

__Returns:__

`Callable[[Callable[..., Any]], Task]`: A callable turning function into task.

__Examples:__

```python
from zrb import python_task
@python_task(
   name='my-task'
)
def my_task(*args, **kwargs):
   return 'hello world'
print(my_task)
```

```
<Task name=my-task>
```


<!--end-doc-->

🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
