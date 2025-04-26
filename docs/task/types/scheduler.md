# Scheduler

The `Scheduler` task is a specialized task type that inherits from `BaseTrigger`. It is designed to trigger other tasks based on a defined schedule using cron-like syntax. When the schedule matches the current time, the `Scheduler` task pushes data (the current time) to its XCom queue, which can then be consumed by a linked `Callback` task.

Here's an example of how to use `Scheduler`:

```python
import asyncio
from zrb import Scheduler, Task, Callback, cli, Context

# Define a simple task that will be triggered by the scheduler
print_scheduled_time = cli.add_task(
    Task(
        name="print-scheduled-time",
        description="Prints the time received from the scheduler",
        # The input 'message' will be mapped from the scheduler's XCom
        input=StrInput(name="message"),
        action=lambda ctx: ctx.print(f"Scheduled task triggered at: {ctx.input.message}"),
    )
)

# Define a Scheduler task that runs every minute
# It pushes the current time to the 'scheduled_events' queue
cli.add_task(
    Scheduler(
        name="minute-scheduler",
        description="Triggers a task every minute",
        schedule="@minutely", # Cron-like schedule pattern (e.g., "@minutely", "* * * * *")
        queue_name="scheduled_events", # The name of the XCom queue to push data to
        # Link the scheduler to the print_scheduled_time task using a Callback
        callback=Callback(
            task=print_scheduled_time,
            # Map the data from the scheduler's XCom queue to the callback task's input
            # {ctx.xcom['scheduled_events'].pop()} retrieves the latest data from the queue
            input_mapping={"message": "{str(ctx.xcom['scheduled_events'].pop())}"},
        ),
    )
)

# You can define other tasks and link them to the same scheduler queue
# For example, another task that logs the event
log_scheduled_event = cli.add_task(
    Task(
        name="log-scheduled-event",
        description="Logs the scheduled event time",
        input=StrInput(name="event_time"),
        action=lambda ctx: ctx.print(f"Logging scheduled event at: {ctx.input.event_time}"),
    )
)

# You can add multiple callbacks to a single trigger/scheduler
cli.get_task("minute-scheduler").append_callback(
    Callback(
        task=log_scheduled_event,
        input_mapping={"event_time": "{str(ctx.xcom['scheduled_events'].pop())}"},
    )
)

# Note: Schedulers are typically long-running tasks that you would run in the background.
# When run, they will continuously check the schedule and trigger callbacks.
```

**When to use**: Use `Scheduler` when you need to automate tasks to run at specific intervals or times based on a cron schedule. It's suitable for recurring jobs, maintenance tasks, or any workflow that needs to be executed periodically.