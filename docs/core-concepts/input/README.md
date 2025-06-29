🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Input](./README.md)

# User Inputs (Input)

Inputs are what make your tasks interactive and dynamic. They allow you to pass parameters to your tasks, whether it's from a user typing on the command line, a selection in the web UI, or even from another task.

Inputs are distinct from environment variables; think of them as function arguments for your tasks, designed for values that change with each run.

You can access the values of your inputs within a task via the `ctx.input` object.

## A Simple Example

Let's create a task that says hello to a specific person.

```python
from zrb import cli, CmdTask, StrInput

cli.add_task(
  CmdTask(
    name="hello",
    input=[
      StrInput(name="name", description="The name to greet"),
      StrInput(name="prefix", description="A title to use", default="Mr./Ms."),
    ],
    cmd="echo 'Hello {ctx.input.prefix} {ctx.input.name}'",
  )
)
```

## Providing Inputs

Zrb gives you two convenient ways to provide inputs to your tasks.

### 1. Command-Line Flags

You can provide inputs directly as command-line flags.

```sh
zrb hello --name Edward --prefix Mr.
# Output: Hello Mr. Edward
```

### 2. Interactive Prompt

If you run the task without providing the required inputs, Zrb will automatically prompt you for them.

```sh
$ zrb hello
? The name to greet: › Edward
? A title to use (Mr./Ms.): › Dr.
Hello Dr. Edward
```

## A Buffet of Input Types

Zrb comes with a variety of input types to handle different kinds of data.

```python
from zrb import Task, StrInput, IntInput, FloatInput, BoolInput, OptionInput, cli

task = Task(
    name="example-task",
    input=[
        StrInput(name="name", description="Your name", default="World"),
        IntInput(name="age", description="Your age", default=30),
        FloatInput(name="height", description="Your height in meters", default=1.75),
        BoolInput(name="subscribe", description="Subscribe to newsletter?", default=True),
        OptionInput(
            name="color",
            description="Favorite color",
            options=["red", "green", "blue"],
            default="blue"
        )
    ],
    action=lambda ctx: print(f"Hello {ctx.input.name}, you are {ctx.input.age} years old.")
)
cli.add_task(task)
```

This rich set of input types allows you to build complex, user-friendly tasks that are both powerful and easy to use.