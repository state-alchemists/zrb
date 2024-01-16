🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Template Rendering

Most Task, Env, and Input properties accept Jinja syntax as a value. Let's see some of them.

## Env

Env has an attribute named `should_render` that defaults to `True`. If this attribute is `True`, Zrb will allow you to put a Jinja syntax as Env's `default` value.

```python
from zrb import runner, Env, CmdTask

task = CmdTask(
    name='task',
    envs=[
        Env(
            name='NOT_RENDERED_ENV',
            default='{{ something }}',
            should_render=False
        ),
        Env(
            name='RENDERED_ENV',
            default='{{ task.get_execution_id() }}',
            should_render=True # The default value
        ),
    ],
    cmd=[
        'echo "NOT_RENDERED_ENV $NOT_RENDERED_ENV"',
        'echo "RENDERED_ENV $RENDERED_ENV"',
    ]
)
runner.register(task)
```

```bash
zrb task
```

```
NOT_RENDERED_ENV {{ something }}
RENDERED_ENV crimson-metallum-07790
```

## EnvFile

EnvFile also has an attribute named `should_render` that defaults to `True`.

If EnvFile's `should_render` is `True`, Zrb will parse the values of your environment file as Jinja syntax.


🔖 [Table of Contents](../README.md) / [Concepts](README.md)
