🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Template Rendering

Most Task, Env, and Input properties accept Jinja syntax as a value. Let's see some of them.

Let's see some available objects in Zrb's Jinja template:

- `datetime`: Python datetime module.
- `os`: Python os module
- `platform`: Python platform module.
- `time`: Python time module.
- `util`: Zrb utilities.
    - `util.coalesce(value, *alternatives)`: Coalesce a value with the alternatives sequentially. An empty string is considered as a value.
    - `util.coalesce_str(value, *alternatives)`: Coalesce a value with the altiernatives sequantially. An empty string is not considered as a value.
    - `util.to_camel-case(text)`: Returns a `camelCased` text.
    - `util.to_pascal_case(text)`: Returns a `PascalCased` text.
    - `util.to_kebab_case(text)`: Returns a `kebab-cased` text.
    - `util.to_snake_case(text)`: Returns a `snake_cased` text.
    - `util.to_human_readable(text)`: Returns a `human readable` text.
    - `util.to_boolean(text)`:
        - Returns `True` if text is either `true`, `1`, `yes`, `y`, `active`, or `on`. 
        - Returns `False` if text is either `fales`, `0`, `no`, `n`, `inactive`, or `off`.
        - Raises Exception otherwise.
- `input`: Input value dictionary. The dictionary keys are __snake_cased__ Input names, while the dictionary values are the rendered Input values.
- `env`: Env value dictionary. The dictionary keys are Env names, while the dictionary values are the rendered Env values. Under the hood, Zrb renders an EnvFile into multiple Envs. Thus, all variables in your environment file will be accessible from the `env` dictionary.
- `task`: Current Task object.
    - `task.get_env_map()`: Returning `env` dictionary.
    - `task.get_input_map()`: Returning `input` dictionary.
    - `task.set_xcom(key, value)`: Returning an empty string after setting an XCom key.
    - `task.get_xcom(key)`: Getting an XCom value.


# Input

Input has an attribute named `should_render` that defaults to `True`. This attribute makes Zrb renders Input's value as a Jinja template.

```python
from zrb import runner, StrInput, CmdTask

task = CmdTask(
    name='task',
    inputs=[
        StrInput(
            name='not-rendered-input',
            default='{{ something }}',
            should_render=False
        ),
        StrInput(
            name='rendered-input',
            default='{{ datetime.datetime.now() }}',
            should_render=True # The default value
        ),
    ],
    cmd=[
        'echo "not-rendered-input {{ input.not_rendered_input }}"',
        'echo "rendered-input {{ input.rendered_input }}"',
    ]
)
runner.register(task)
```

```bash
zrb task
```

```
not-rendered-input {{ something }}
rendered-input 2024-01-16 08:25:27.325030
```

# Env

Env has an attribute named `should_render` that defaults to `True`. This attributes makes Zrb renderes Env's `default` value as Jinja template.

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

# EnvFile

EnvFile also has an attribute named `should_render` that defaults to `True`.

If EnvFile's `should_render` is `True`, Zrb will parse the environment values in your environment file as Jinja syntax.


🔖 [Table of Contents](../README.md) / [Concepts](README.md)
