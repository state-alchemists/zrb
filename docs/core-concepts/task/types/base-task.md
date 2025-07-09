🔖 [Home](../../../README.md) > [Documentation](../../../README.md) > [Core Concepts](../../README.md) > [Task](../README.md) > [Task Types](./README.md) > BaseTask

# `BaseTask`

The `BaseTask` is the ancestor of all other task types in Zrb. It's the foundational class that provides the core engine for executing tasks. While you can use `BaseTask` for almost anything, Zrb offers more specialized task types (like `CmdTask`, `LLMTask`, etc.) that are often more convenient for specific jobs.

You'll most often interact with its alias, `Task`, for running general Python code. `BaseTask` is what gives all tasks their common powers: inputs, environment variables, dependencies, retries, and more.

## `BaseTask` in Action

Here’s a comprehensive example showcasing the versatility of `BaseTask`.

```python
import asyncio
from zrb import BaseTask, IntInput, StrInput, Env, Context, cli, Group

# A simple BaseTask running a lambda function
cli.add_task(
    BaseTask(
        name="simple-greeting",
        description="Prints a simple greeting",
        action=lambda ctx: ctx.print("Hello from a simple task!")
    )
)

# A BaseTask with inputs and environment variables
cli.add_taks(
    BaseTask(
        name="greet-user",
        description="Greets a user with a custom message",
        input=[
            StrInput(name="user_name", description="The name of the user"),
            IntInput(name="repeat_count", description="How many times to greet", default=1),
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

# A BaseTask with an asynchronous action and a dependency
async def async_action_example(ctx: Context):
    ctx.print("Starting async action...")
    await asyncio.sleep(1)
    ctx.print("Async action finished.")
    return "Async result"

async_task = BaseTask(
    name="async-example",
    action=async_action_example
)

dependent_task = BaseTask(
    name="dependent-task",
    description="Runs after async-example and uses its result",
    upstream=[async_task],
    action=lambda ctx: ctx.print(f"Received result: {ctx.xcom['async-example'].pop()}")
)

cli.add_task(dependent_task)

# A BaseTask with a fallback
fallback_task = BaseTask(
    name="cleanup-on-failure",
    action=lambda ctx: ctx.print("Executing fallback cleanup!")
)

cli.add_task(
    BaseTask(
        name="risky-task",
        description="A task that is designed to fail",
        action=lambda ctx: 1 / 0,  # This will raise a ZeroDivisionError
        fallback=fallback_task
    )
)

# A BaseTask with a readiness check
check_service_ready = BaseTask(
    name="service-ready-check",
    action=lambda ctx: print("Checking service...") or True  # Simulate a check
)

cli.add_task(
    BaseTask(
        name="use-service",
        description="Uses a service after it's ready",
        action=lambda ctx: ctx.print("Service is ready, proceeding!"),
        readiness_check=check_service_ready,
        readiness_timeout=10,  # Wait up to 10 seconds
        readiness_check_period=2  # Check every 2 seconds
    )
)
```

This example illustrates how `BaseTask` serves as a flexible foundation for all kinds of actions, from simple print statements to complex, asynchronous workflows with error handling and service checks.