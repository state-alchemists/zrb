🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Input](./README.md)

# Input

Use `task`'s `input` to get user inputs.

You can access `input` by using `ctx.input` property.

```python
from zrb import cli, CmdTask, StrInput

cli.add_task(
  CmdTask(
    name="hello",
    input=[
      StrInput(name="name"),
      StrInput(name="prefix"),
    ],
    cmd="echo Hello {ctx.input.prefix} {ctx.input.name}",
  )
)
```

You can run the task while providing the inputs, or you can trigger the interactive session.

```sh
zrb hello --name Edward --prefix Mr
# or
zrb hello
```

```
Hello Mr Edward
```

Inputs allow tasks to receive parameters from users or other tasks, providing flexibility and interactivity. They are distinct from environment variables, which are typically used for configuration.

Zrb provides several input types:

```python
from zrb import Task, StrInput, IntInput, FloatInput, BoolInput, OptionInput, cli

task = Task(
    name="example-task",
    input=[
        StrInput(name="name", description="Your name", default="World"),
        IntInput(name="age", description="Your age", default=30),
        FloatInput(name="height", description="Your height in meters", default=1.75),
        BoolInput(name="subscribe", description="Subscribe to newsletter", default=True),
        OptionInput(
            name="color",
            description="Favorite color",
            options=["red", "green", "blue"],
            default="blue"
        )
    ],
    action=lambda ctx: print(f"Hello {ctx.input.name}, you are {ctx.input.age} years old")
)
cli.add_task(task)  # Don't forget to register the task
```

Inputs can be accessed in the task's action via the `ctx.input` object.