🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Environments

You can use `envs` and `env_files` attributes to define Task Environments.

Let's see the following example:

```python
from zrb import runner, Env, CmdTask

hello = CmdTask(
    name='hello',
    envs=[
        Env(
            name='USER_NAME',
            os_name='USER',
            default='Employee'
        )
    ],
    cmd='echo $USER_NAME',
)
runner.register(hello)
```

In the example, you define an environment named `USER_NAME`. This environment is linked to the operating system `USER` environment. If the value of `USER` environment is not set, Zrb will use the default value `Employee`.

You can also set `os_name` to an empty string (i.e., `''`) to avoid association with the operating system's environment. If you set `os_name` to empty, then Zrb will always use the `default` value of the environment.

To access the environment variable, you can use `$USER_NAME`. Alternatively, you can also use the Jinja Template `{{ env.USER_NAME }}`.

As for `@python_task`, you can access Task Environment using `kwargs['_task'].get_env_map()`. Let's see the following example:


```python
from zrb import runner, Env, python_task, Task

@python_task(
    name='hello',
    envs=[
        Env(
            name='USER_NAME',
            os_name='USER',
            default=''Employee'
        )
    ],
    runner=runner
)
def hello(*args, **kwargs) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    user_name = env_map.get('USER_NAME')
    return f'Hello {user_name}'
```

Notice that Zrb is not altering your `os.environ`, so you cannot use a typical `os.getenv('USER_NAME')` here. This behavior is intentional since we want every Task to be isolated from each other.


🔖 [Table of Contents](../README.md) / [Concepts](README.md)
