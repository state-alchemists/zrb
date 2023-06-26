🔖 [Table of Contents](../README.md) / [Concepts](README.md)

# Template

You can use Jinja template for task input's default value, task environment' default value, and several task's properties.

# Common render data

There are some common render data you can use:

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

# Render data for input default value

You can use all common render data for your input default value.

For example:

```python
from zrb import CmdTask, runner, StrInput:

pull_image = CmdTask(
    name='pull-image',
    inputs=[
        StrInput(
            name='image-name',
            default='docker.io/gofrendi/{{util.to_kebab_case(input.app_name)}}'
        )
    ],
    cmd='docker pull {{input.image_name}}'
)
```

# Render data for environment default value

You can use all common render data for you environment default value. Additionally, you can access `input` value as well.

Notice that input name will be automatically snake-cased, for example:

```python
from zrb import CmdTask, runner, StrInput, Env:

pull_image = CmdTask(
    name='pull-image',
    inputs=[
        StrInput(
            name='image-name',
            default='docker.io/gofrendi/{{util.to_kebab_case(input.app_name)}}'
        )
    ],
    envs=[
        Env(name='IMAGE', default='{{input.image_name}}')
    ]
    cmd=[
        'echo "pulling $IMAGE"',
        'docker pull $IMAGE'
    ]
)
``` 

# Render data for task properties

As for task properties, you can use all common render data, along with `input` and `env`.

For example:

```python
from zrb import CmdTask, runner

demo = CmdTask(
    name='demo',
    inputs=[
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
        'echo {% for arg in input._args %}{{ arg }}{% endfor %}',
        'echo Image name (via input): {{ input.image_name }}',
        'echo Image name (via env): {{ env.IMAGE }}',
        'echo Image name (via env variable): $IMAGE',
    ]
)
runner.register(demo)
```

You can try to invoke:

```
zrb demo --image-name docker.io/my-image one two three
```

🔖 [Table of Contents](../README.md) / [Concepts](README.md)
