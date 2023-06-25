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

# CmdTask parameters

Every [task parameters](./task.md#common-task-parameters) are applicable here. Additionally, a `CmdTask` has it's own specific parameters.

## `executable`

## `cmd`

## `cmd_path`

## `cwd`

## `max_output_line`

## `max_error_line`

## `preexec_fn`

# CmdTask methods

Please refer to [common task methods](./README.md#common-task-methods).


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)
