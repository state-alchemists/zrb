🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Template

You can use [Jinja template](https://jinja.palletsprojects.com/en/3.1.x/templates) for
- task input's default value
- task environment's default value
- several task's properties like `cmd`, `cmd_path`, `setup_cmd`, etc.

There are several render data you can use. Some are always available, while some others are only available in specific properties

# Common render data

The following render data are always available:

- `datetime`: Python datetime module
- `os`: Python os module
- `platform`: Python platform module
- `time`: Python time module
- `util`: Containing several utility function:
    - `coalesce(value, *alternatives)`: you can use this function to coalesce value with alternatives
    - `coalesce_str(value, *alternatives)`: Same as `util.coalesce`, but empty string is treated as `None` or `undefined`
    - `to_camel_case(text)`: Return a `camelCased` text.
    - `to_pascal_case(text)`: Return a `PascalCased` text.
    - `to_kebab_case(text)`: Return a `kebab-cased` text.
    - `to_snake_case(text)`: Return a `snake_cased` text.
    - `to_human_readable(text)`: Return a `human readable` text.
    - `to_boolean(text)`: Convert text to boolean. This function handle case-insensitive text, but it will throw an error if the text is neither true/false value representation.
        - True value: `true`, `1`, `yes`, `y`, `active`
        - False value: `false`, `0`, `0`, `n`, `inactive`

# Specific render data


- `input`: Map representation task input's value. Accessible when you set `task environment`'s property or any `task` property.
    - `<snake_case_key>`: All task key inputs are snake-cased. These keys are accessible when you set `task environment`'s default property or any `task` property.
    - `_task`: Representation of current task object, only accessible from `task` property
    - `_kwargs`: Map representation of current task input keyword arguments, only accessible from `task` property
    - `_args`: List representation of current task input arguments, only accessible from `task` property
- `env`: Map representation of task environment. Only accessible from task property.

# Example

```python
from zrb import CmdTask, StrInput, Env, runner

demo = CmdTask(
    name='demo',
    inputs=[
        StrInput(
            name='app-name',
            default='my-app'
        ),
        StrInput(
            name='image-name',
            default='docker.io/gofrendi/{{util.to_kebab_case(input.app_name)}}'
        )
    ],
    envs=[
        Env(name='IMAGE', default='{{input.image_name}}')
    ],
    cmd=[
        'echo {{ input._args.0 }}',
        '{% for arg in input._args %}echo "{{ arg }} ";{% endfor %}',
        'echo "Image name (via input): {{ input.image_name }}"',
        'echo "Image name (via env): {{ env.IMAGE }}"',
        'echo "Image name (via env variable): $IMAGE"',
    ]
)
runner.register(demo)
```

You can try to invoke:

```
zrb demo --app-name my-app one two three
```

The result will be:

```
one
one
two
three
Image name (via input): docker.io/my-app
Image name (via env): docker.io/my-app
Image name (via env variable): docker.io/my-app
```

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
