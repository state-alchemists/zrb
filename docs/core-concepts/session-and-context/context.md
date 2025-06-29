🔖 [Home](../../../README.md) > [Documentation](../../../../README.md) > [Core Concepts](../../README.md) > [Session and Context](./README.md) > [Context](./context.md)

# Context

The `Context` object, typically accessed via the `ctx` parameter in a task's `action` method, is the primary interface through which a task interacts with its execution environment and accesses data. It provides a combination of information shared across all tasks in a session and details specific to the currently running task.

Understanding the `Context` object is crucial for writing tasks that can access inputs, environment variables, exchange data with other tasks, log information, and utilize rendering capabilities.

The `Context` object is composed of two main parts: the Shared Context and the Task-Specific Context.

## Shared Context (`ctx.shared_ctx`)

The Shared Context holds information that is available and consistent across all tasks within the same session. While you can access these properties directly via the `ctx` object (e.g., `ctx.input`), they are technically part of the shared context.

Key properties available in the Shared Context:

*   `ctx.input`: Access to the task's defined inputs, provided by the user or other sources. See the [Inputs documentation](input.md) for more details.
*   `ctx.env`: Access to environment variables available to the task, including those from the system, `.env` files, and task definitions. See the [Environment Variables documentation](env.md) for more details.
*   `ctx.args`: Access to any positional arguments passed to the task from the command line.
*   `ctx.xcom`: Access to the XCom (Cross-Communication) queues for exchanging data between tasks. See the [XCom documentation](xcom.md) for more details.
*   `ctx.shared_log`: A list containing all log messages generated across all tasks in the session.
*   `ctx.session`: A reference to the current `Session` object managing the task execution. See the [Session documentation](session.md) for more details.

## Task-Specific Context

The Task-Specific Context provides functionalities and information relevant only to the currently executing task.

Key methods and properties available in the Task-Specific Context:

*   `ctx.print(*values, ...)`: A method for printing output from the task. This method often includes formatting and task-specific prefixes (like task name and color) in the CLI output.
*   Logging Methods (`ctx.log_debug`, `ctx.log_info`, `ctx.log_warning`, `ctx.log_error`, `ctx.log_critical`): Methods for logging messages at different severity levels. These messages are also added to the `ctx.shared_log`.
*   Rendering Methods (`ctx.render`, `ctx.render_bool`, `ctx.render_int`, `ctx.render_float`): Methods for rendering template strings (using Jinja2 syntax) with access to context data (inputs, env, xcom, etc.). Useful for dynamically generating strings, booleans, integers, or floats based on the session's state.
*   `ctx.set_attempt(attempt)` and `ctx.set_max_attempt(max_attempt)`: Methods used internally by the Zrb runner to update the task's attempt count, particularly relevant for tasks configured with retries.
*   `ctx.update_task_env(task_env)`: Method to update the task's environment variables dynamically during execution.

## Example

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

        # Pushing data to XCom (if needed for downstream tasks)
        ctx.xcom[ctx.task_name].push("Task completed successfully")
    )
)

cli.add_task(example_task)
```

The `Context` object provides a powerful way for your tasks to be dynamic and interact with the Zrb execution environment.