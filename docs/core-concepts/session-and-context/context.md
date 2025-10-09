🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Core Concepts](../README.md) > [Session and Context](./README.md) > [Context](./context.md)

# The Context (`ctx`)

The `Context` object, almost always referred to as `ctx` in a task's `action` method, is your task's window to the world. It's the primary way a task interacts with its execution environment, accesses data, and performs essential operations like logging and rendering.

Think of `ctx` as a toolkit that Zrb hands to your task right before it runs. Understanding this toolkit is key to unlocking the full potential of your Zrb automations.

The `Context` is a clever blend of two types of information: data that's shared across all tasks in a run, and functions that are specific to the current task.

## Shared Context (`ctx.shared_ctx`)

The Shared Context holds information that is available and consistent across all tasks within the same session. While you can access these properties directly via `ctx` (e.g., `ctx.input`), it's useful to know they are part of a shared state.

Key properties available in the Shared Context:

*   `ctx.input`: Access user-provided values. See the [Inputs documentation](../input/README.md) for more.
*   `ctx.env`: Access environment variables. See the [Environment Variables documentation](../env/README.md) for more.
*   `ctx.args`: Access any positional arguments passed to the task from the command line.
*   `ctx.xcom`: Access the data-sharing queues. See the [XCom documentation](./xcom.md) for more.
*   `ctx.shared_log`: A list of all log messages from all tasks in the session.
*   `ctx.session`: A reference to the current `Session` object. See the [Session documentation](./session.md) for more.

## Task-Specific Context

This part of the `Context` provides functions and information relevant only to the currently executing task.

Key methods and properties:

*   `ctx.print(*values, ...)`: The standard way to print output from your task. It often adds helpful formatting, like the task's name and color, to the output.
*   Logging Methods (`ctx.log_debug`, `ctx.log_info`, etc.): A suite of methods for logging messages at different severity levels. These messages are also captured in `ctx.shared_log`.
*   Rendering Methods (`ctx.render`, `ctx.render_bool`, etc.): Powerful methods for rendering Jinja2 template strings. You can dynamically generate strings, booleans, or numbers using data from the context (inputs, env, xcom).
*   `ctx.set_attempt(attempt)` and `ctx.set_max_attempt(max_attempt)`: Methods used internally by Zrb for tasks with retry logic.
*   `ctx.update_task_env(task_env)`: A method to dynamically update the task's environment variables during execution.

## Example in Action

Let's see how you might use the `ctx` object in a real task.

```python
from zrb import Task, StrInput, Env, cli

example_task = Task(
    name="context-example",
    description="Demonstrates accessing context information",
    input=StrInput(name="greeting", default="Hello"),
    env=[Env(name="TARGET", default="World")],
    action=lambda ctx: (
        # Accessing shared context properties
        ctx.print(f"{ctx.input.greeting}, {ctx.env.TARGET}!"),
        ctx.print(f"Task name: {ctx.task_name}"),
        ctx.print(f"Session name: {ctx.session.name}"),

        # Using logging methods
        ctx.log_info("This is an info message."),
        ctx.log_debug("This is a debug message."),

        # Using rendering methods
        message_template = "{ctx.input.greeting} from {ctx.task_name}",
        rendered_message = ctx.render(message_template),
        ctx.print(f"Rendered message: {rendered_message}"),

        # Pushing data to XCom for other tasks to use
        ctx.xcom[ctx.task_name].push("Task completed successfully")
    )
)

cli.add_task(example_task)
```

Mastering the `Context` object is a huge step towards writing dynamic, powerful, and well-integrated Zrb tasks.