🔖 [Documentation Home](../../../README.md) > [Task](../../README.md) > [Task Types](../README.md) > BaseTask

# BaseTask

The `BaseTask` is the fundamental building block for all other task types in Zrb. It provides the core structure and capabilities for defining and executing tasks. While `BaseTask` is highly versatile and can technically handle most use cases, Zrb offers more specialized task types (like `CmdTask`, `LLMTask`, `Scaffolder`, etc.) that are often more convenient and provide domain-specific features. You will typically use these specialized tasks or the simple `Task` alias (which is just a `BaseTask`) for most of your needs.

`BaseTask` can execute Python functions or expressions using the `action` parameter. It also supports defining inputs, environment variables, dependencies (upstreams, fallbacks, successors), readiness checks, retries, and execution conditions.

The preferred way to define and register a task is by passing the task instance directly to `cli.add_task()` or a group's `add_task()` method.

Here's a detailed example demonstrating various features of `BaseTask` using the preferred registration convention:

```python
import asyncio
from zrb import BaseTask, IntInput, StrInput, Env, Context, cli, Group

# A simple BaseTask running a lambda function
cli.add_task(
    BaseTask(
        name="simple-greeting",
        description="Prints a simple greeting",
        action=lambda ctx: ctx.print("Hello from simple_task!")
    )
)

# A BaseTask with inputs and environment variables
cli.add_task(
    BaseTask(
        name="greet-user",
        description="Greets a user with a custom message and environment variable",
        input=[
            StrInput(name="user_name", description="The name of the user to greet"),
            IntInput(name="repeat_count", description="How many times to repeat the greeting", default=1),
        ],
        env=[
            Env(name="GREETING_PREFIX", default="Hi"),
        ],
        action=lambda ctx: [
            ctx.print(f"{ctx.env.GREETING_PREFIX}, {ctx.input.user_name}!")
            for _ in range(ctx.input.repeat_count)
        ]
    )
)

# A BaseTask with an asynchronous action and dependencies
async def async_action_example(ctx: Context):
    ctx.print("Starting asynchronous action...")
    await asyncio.sleep(1)
    ctx.print("Asynchronous action finished.")
    return "Async result"

async_task_instance = BaseTask(
    name="async-example",
    description="An example of an asynchronous task",
    action=async_action_example
)

# Another task that depends on async_task_instance
dependent_task_instance = BaseTask(
    name="dependent-task",
    description="Runs after async-example and uses its result",
    action=lambda ctx: ctx.print(f"Dependent task received result: {ctx.xcom['async-example'].pop()}")
)

dependent_task_instance.append_upstream(async_task_instance)

# Register dependent_task_instance (which also makes async_task_instance accessible)
cli.add_task(dependent_task_instance)


# A BaseTask with a fallback task
fallback_task_instance = BaseTask(
    name="cleanup-on-failure",
    description="Runs if the main task fails",
    action=lambda ctx: ctx.print("Executing fallback cleanup!")
)

cli.add_task(
    BaseTask(
        name="risky-task",
        description="A task that might fail",
        action=lambda ctx: 1 / 0, # This will cause a ZeroDivisionError
        fallback=fallback_task_instance
    )
)

# A BaseTask with a readiness check
check_service_ready_instance = BaseTask(
    name="service-ready-check",
    description="Checks if a hypothetical service is ready",
    action=lambda ctx: print("Checking service...") or True # Simulate a check
)

cli.add_task(
    BaseTask(
        name="use-service",
        description="Uses a service after it's ready",
        action=lambda ctx: ctx.print("Service is ready, proceeding!"),
        readiness_check=check_service_ready_instance,
        readiness_timeout=10, # Wait up to 10 seconds
        readiness_check_period=2 # Check every 2 seconds
    )
)

# Example of adding a BaseTask to a group
example_group = cli.add_group(Group("example-group", description="An example group"))

example_group.add_task(
    BaseTask(
        name="task-in-group",
        description="A BaseTask within a group",
        action=lambda ctx: ctx.print("Hello from a task in a group!")
    )
)
```

This example demonstrates how `BaseTask` can be used for various purposes, including simple actions, handling inputs and environment variables, managing asynchronous operations, defining dependencies, implementing fallback logic, incorporating readiness checks, and being added to groups. Remember that for common patterns like running shell commands or interacting with LLMs, using the dedicated `CmdTask` or `LLMTask` is generally recommended for clarity and built-in features.