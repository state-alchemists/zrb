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
    - `util.coalesce_str(value, *alternatives)`: Coalesce a value with the alternatives sequantially. An empty string is not considered as a value.
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
    - `task.get_execution_id()`: Getting Execution ID


# Input

Input has an attribute named `should_render` that defaults to `True`. This attribute makes Zrb render Input's value as a Jinja template.

The following objects are accessible from Input's value:

- `datetime`
- `os`
- `platform`
- `time`
- `util`
- `input` (Only the preceding inputs's values are accessible)
- `task.get_execution_id()`

Let's see an example.


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

Env has an attribute named `should_render` that defaults to `True`. This attribute makes Zrb render Env's `default` value as a Jinja template.

The following objects are accessible from Env's value:

- `datetime`
- `os`
- `platform`
- `time`
- `util`
- `input`
- `env` (Only the preceding Env's values are accessible)
- `task.get_execution_id()`

Let's see an example.


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

EnvFile has an attribute named `should_render` that defaults to `True`. This attribute makes Zrb render the environment variable's values in your as a Jinja template.

The following objects are accessible from the environment variable's value:

- `datetime`
- `os`
- `platform`
- `time`
- `util`
- `input`
- `env` (Only the preceding Env's values are accessible) 
- `task.get_execution_id()`

Let's see an example.


```bash
# file-name: a.env
NOT_RENDERED_ENV="{{ something }}"
```

```bash
# file-name: b.env
RENDRED_ENV="{{ task.get_execution_id() }}"
```

```python
from zrb import runner, EnvFile, CmdTask

import os

CURRENT_DIR = os.dirname(__file__)

task = CmdTask(
    name='task',
    env_files=[
        EnvFile(
            path=os.path.join(CURRENT_DIR, 'a.env'),
            should_render=False
        ),
        EnvFile(
            path=os.path.join(CURRENT_DIR, 'b.env')
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

# Task Attributes

All template objects are accessible from the following Task Properties. When in doubt, you can check on the properties annotation. Anything with `JinjaTemplate` are renderable.

## BaseTask

Zrb renders the following attributes as Jinja Template:

- `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)

Example:

```python
from zrb import runner, BoolInput, Task

task = Task(
    name='task',
    inputs=[
        BoolInput(name='should-execute', default=True)
    ],
    should_execute='{{ input.should_execute }}'
)
runner.register(task)
```

## CmdTask

Zrb renders the following attributes as Jinja Template:

- `cmd` (`CmdVal`)
- `cmd_path` (`CmdVal`)
- `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)

Example:

```python
from zrb import runner, BoolInput, StrInput, CmdTask

task = CmdTask(
    name='task',
    inputs=[
        BoolInput(name='should-execute', default=True),
        StrInput(name='name', default='World')
    ],
    should_execute='{{ input.should_execute }}',
    cmd='echo "{{ input.name }}"'
)
runner.register(task)
```

## RemoteCmdTask

Zrb renders the following attributes as Jinja Template:

- `cmd` (`CmdVal`)
- `cmd_path` (`CmdVal`)
- `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)

Furthermore, Zrb also renders [`remote_configs`](#remoteconfig) attributes as Jinja Template.

Example:

```python
from zrb import runner, BoolInput, StrInput, PasswordInput, RemoteCmdTask, RemoteConfig

task = RemoteCmdTask(
    name='task',
    inputs=[
        BoolInput(name='should-execute', default=True),
        StrInput(name='name', default='World'),
        StrInput(name='server-1-host', default='stalchmst.com'),
        StrInput(name='server-1-user', default='root'),
        PasswordInput(name='server-1-pass'),
        StrInput(name='server-2-host', default='contoso.com'),
        StrInput(name='server-2-user', default='root'),
        PasswordInput(name='server-2-pass')
    ],
    remote_configs=[
        RemoteConfig(
            host='{{ input.server_1_host }}',
            user='{{ input.server_1_user }}',
            password='{{ input.server_1_pass }}'
        ),
        RemoteConfig(
            host='{{ input.server_2_host }}'
            user='{{ input.server_2_user }}',
            password='{{ input.server_2_pass }}'
        ),
    ],
    should_execute='{{ input.should_execute }}',
    cmd='echo "{{ input.name }}" && uname -a'
)
runner.register(task)
```

## RsyncTask

Zrb renders the following attributes as Jinja Template:

- `src` (`JinjaTemplate`)
- `dst` (`JinjaTemplate`)

Furthermore, Zrb also renders [`remote_configs`](#remoteconfig) attributes as Jinja Template.

## RemoteConfig

Zrb renders the following attributes as Jinja Template:

- `host` (`JinjaTemplate`)
- `user` (`JinjaTemplate`)
- `password` (`JinjaTemplate`)
- `ssh_key` (`JinjaTemplate`)
- `port` (`JinjaTemplate`)
- `config_map` (`Mapping[str, JinjaTemplate]`)


## DockerComposeTask

Zrb renders the following attributes as Jinja Template:

- `compose_options` (`Mapping[JinjaTemplate, JinjaTemplate]`)
- `compose_flags` (`Iterable[JinjaTemplate]`)
- `compose_args` (`Iterable[JinjaTemplate]`)
- `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)
- `setup_cmd` (`CmdVal`)
- `setup_cmd_path` (`CmdVal`)

Example:

```python
from zrb import runner, BoolInput, IntInput, DockerComposeTask

task = DockerComposeTask(
    name='task',
    inputs=[
        BoolInput(name='should-execute', default=True),
        IntInput(name='uid', default=1000)
    ],
    should_execute='{{ input.should_execute }}',
    compose_cmd='up',
    compose_options={
        '-u': '{{ input.uid }}'
    }
)
runner.register(task)
```

## ResourceMaker

Zrb renders the following attributes as Jinja Template:

- `template_path` (`JinjaTemplate`)
- `destination_path` (`JinjaTemplate`)
- `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)

Furthermore, Zrb also renders the `replacements` attribute values as Jinja Template.

Example:

```python
from zrb import runner, BoolInput, StrInput, ResourceMaker
import os

CURRENT_DIR = os.path.dirname(__file__)

task = ResourceMaker(
    name='task',
    template_path=os.path.join(CURRENT_DIR, 'template'),
    inputs=[
        StrInput(name='project-dir', default='.'),
        StrInput(name='project-name', default='new_project')
    ],
    destination_path='{{ input.project_dir }}',
    replacements={
        'project_name': '{{ input.project_name }}'
    }
)
runner.register(task)
```


## Notifier

Zrb renders the following attributes as Jinja Template:

- `title` (`JinjaTemplate`)
- `message` (`JinjaTemplate`)

Example:

```python
from zrb import Runner, StrInput, Notifier

task = Notifier(
    name='task',
    inputs=[
        StrInput(name='title', default='Notification'),
        StrInput(name='message', default='Message'),
    ],
    title='{{ input.title }}',
    message='{{ input.message }}',
)
runner.register(task)
```

## Checkers

Zrb renders Checker attributes as Jinja Template. The detailed renderable attributes are as follows:

- `TimeWatcher`
    - `schedule` (`JinjaTemplate`)
    - `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)
- `HTTPChecker`
    - `host` (`JinjaTemplate`)
    - `port` (`Union[JinjaTemplate, int]`)
    - `timeout` (`Union[JinjaTemplate, int]`)
    - `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)
- `PortChecker` 
    - `host` (`JinjaTemplate`)
    - `port` (`Union[JinjaTemplate, int]`)
    - `timeout` (`Union[JinjaTemplate, int]`)
    - `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)
- `PathChecker`
    - `path` (`JinjaTemplate`)
    - `ignored_path` (`Union[Iterable[JinjaTemplate], JinjaTemplate]`)
    - `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)
- `PathWatcher`
    - `path` (`JinjaTemplate`)
    - `ignored_path` (`Union[Iterable[JinjaTemplate], JinjaTemplate]`)
    - `should_execute` (`Union[bool, JinjaTemplate, Callable[..., bool]]`)


🔖 [Table of Contents](../README.md) / [Concepts](README.md)
