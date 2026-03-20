"""
Trigger and Scheduler Example

Shows how to create event-driven and scheduled tasks.

- Triggers: Fire on custom events (queue-based)
- Schedulers: Fire on time intervals (cron-like)
"""

import asyncio

from zrb import AnyContext, BaseTrigger, Callback, Scheduler, StrInput, Task, Xcom, cli

# =============================================================================
# Basic Trigger
# =============================================================================

# A trigger fires when something happens and can call a callback task


async def trigger_action(ctx: AnyContext):
    """Action that pushes values to a queue."""
    xcom: Xcom = ctx.xcom["my-queue"]

    for i in range(5):
        ctx.print(f"Pushing {i} to queue...")
        xcom.push(i)
        await asyncio.sleep(0.5)

    ctx.print("✅ Trigger complete")


# Task to run when trigger fires
print_task = cli.add_task(
    Task(
        name="print",
        input=StrInput(name="message", default=""),
        action=lambda ctx: ctx.print(f"📨 Received: {ctx.input.message}"),
    )
)

# Trigger that runs action and calls print_task for each queue item
cli.add_task(
    BaseTrigger(
        name="queue-trigger",
        queue_name="my-queue",
        action=trigger_action,
        callback=Callback(
            task=print_task,
            input_mapping={"message": "{ctx.xcom['my-queue'].pop()}"},
        ),
    )
)

# =============================================================================
# Scheduler (Cron-like)
# =============================================================================

# Schedules run on a time interval


cli.add_task(
    Scheduler(
        name="minutely",
        schedule="@minutely",  # Every minute
        queue_name="minute-queue",
        callback=Callback(
            task=print_task,
            input_mapping={"message": "{str(ctx.xcom['minute-queue'].pop())}"},
        ),
    )
)


# Schedule options
cli.add_task(
    Scheduler(
        name="hourly",
        schedule="@hourly",  # Every hour
        queue_name="hour-queue",
        callback=Callback(
            task=print_task,
            input_mapping={"message": "Hourly check!"},
        ),
    )
)


# Cron expression: every 5 minutes
cli.add_task(
    Scheduler(
        name="every-5min",
        schedule="*/5 * * * *",  # Cron syntax
        queue_name="5min-queue",
        callback=Callback(
            task=print_task,
            input_mapping={"message": "5 minute check!"},
        ),
    )
)

# =============================================================================
# Trigger with Multiple Callbacks
# =============================================================================


async def multi_trigger(ctx: AnyContext):
    """Push multiple items with metadata."""
    xcom = ctx.xcom["multi-queue"]

    xcom.push({"type": "user", "name": "Alice"})
    xcom.push({"type": "user", "name": "Bob"})
    xcom.push({"type": "system", "name": "Backup"})

    ctx.print("Pushed 3 items to multi-queue")


multi_print = cli.add_task(
    Task(
        name="multi-print",
        input=StrInput(name="data"),
        action=lambda ctx: ctx.print(f"📦 Data: {ctx.input.data}"),
    )
)

cli.add_task(
    BaseTrigger(
        name="multi-trigger",
        queue_name="multi-queue",
        action=multi_trigger,
        callback=Callback(
            task=multi_print,
            input_mapping={"data": "{str(ctx.xcom['multi-queue'].pop())}"},
        ),
    )
)

# =============================================================================
# Manual Trigger Example
# =============================================================================

# You can also manually push to queues


manual_trigger = cli.add_task(
    Task(
        name="manual-trigger",
        action=lambda ctx: ctx.print("Manual trigger fired!"),
    )
)
