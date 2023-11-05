🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# CmdTask

You can use CmdTask to run CLI commands.

Let's see the following example:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd='echo {{input.name}}'
)
runner.register(say_hello)
```

If you need a multi-line command, you can also define the command as a list:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd=[
        'echo {{input.name}}',
        'echo $_INPUT_NAME', # This will also works
        'echo Yeay!!!'
    ]
)
runner.register(say_hello)
```

However, if your command is too long, you can also load it from another file:


```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd_path='hello_script.sh'
)
runner.register(say_hello)
```

You can then run the task by invoking:

```bash
zrb say-hello --name=John
```

# CmdTask Parameters

Every [task parameters](./task.md#common-task-parameters) are applicable here. Additionally, a `CmdTask` has it's own specific parameters.

## `executable`

Executable to run `cmd` command.

- __Required:__ False
- __Possible values:__ String representing the terminal, for example `bash` or `zsh`.
- __Default value:__ Equals to `ZRB_SHELL` If set. Otherwise it will be `bash`.


## `cmd`

The command to be executed.

Note that your command migt contains Jinja template. For example, you can use `{{input.snake_input_name}}` or `{{env.ENV_NAME}}`.

Additionaly, task inputs are assigned as terminal environment variable, uppercased with `_INPUT_` prefix.

Let's see on the following example:

```python
from zrb import CmdTask, StrInput, Env, runner

say_hello = CmdTask(
    name='say-hello',
    inputs=[
        StrInput(name='name')
    ],
    envs=[
        Env(name='SOME_ENV')
    ],
    cmd=[
        'echo {{input.name}}',
        'echo $_INPUT_NAME',
        'echo {{env.SOME_ENV}}',
        'echo $SOME_ENV',
        'echo Yeay!!!'
    ]
)
runner.register(say_hello)
```

- __Required:__ False
- __Possible values:__ 
    - String representing the command
    - List of string representing multiline command
    - Function returning a string
- __Default value:__ Empty string.


## `cmd_path`

String representing path of the shell script. If set, this will override `cmd`.

- __Required:__ False
- __Possible values:__ String representing shell script location.
- __Default value:__ Empty string.

## `cwd`

String representing current working directory.

- __Required:__ False
- __Possible values:__ String representing current working directory.
- __Default value:__ `None`

## `max_output_line`

How many line of output to be shown

- __Required:__ False
- __Possible values:__ Integer value.
- __Default value:__ `1000`

## `max_error_line`

How many line of error to be shown

- __Required:__ False
- __Possible values:__ Integer value.
- __Default value:__ `1000`

## `preexec_fn`

Function to set process `sid`.

- __Required:__ False
- __Possible values:__ function to set `sid` or `None`.
- __Default value:__ `os.setsid`.

# CmdTask methods

Please refer to [common task methods](./README.md#common-task-methods).


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
