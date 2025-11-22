🔖 [Home](../../../../../README.md) > [Documentation](../../../../README.md) > [Core Concepts](../../../README.md) > [Task](../../README.md) > [Types](../README.md)

# Trigger and Scheduler

While most tasks run once and then complete, Zrb also supports long-running tasks that can react to events or run on a schedule. These are built on two key components: the `BaseTrigger` and the `Scheduler`.

## `BaseTrigger`: The Foundation for Event-Driven Tasks

A `BaseTrigger` is a special type of task that listens for internal events and triggers other tasks (called `callbacks`) in response. It's the foundation of Zrb's event-driven architecture.

### How It Works

1.  **Listens on a Queue**: A `BaseTrigger` monitors an `XCom` queue, which is identified by its `queue_name`.
2.  **Waits for Data**: It waits for another task or process to push data into that queue.
3.  **Triggers Callbacks**: When data is received, the `BaseTrigger` immediately executes its `callback` tasks, passing the received data to them.

This creates a powerful publish-subscribe (pub/sub) system inside Zrb, allowing you to build reactive workflows.

### Example: A Manual Trigger

Here's a scenario where we manually trigger a `callback` task by pushing data to its queue.

```python
from zrb import cli, Group, CmdTask, BaseTrigger, StrInput

# The callback task that will be triggered
email_sender = CmdTask(
    name="send-email",
    input=StrInput(name="message"),
    cmd="echo 'Sending email with message: {ctx.input.message}'"
)

# The trigger task that waits for a message
email_trigger = BaseTrigger(
    name="email-trigger",
    description="Waits for a message to send an email",
    queue_name="email_queue",
    callback=email_sender
)

# A task to manually push a message to the trigger's queue
push_message = CmdTask(
    name="push-message",
    description="Pushes a message to the email queue",
    input=StrInput(name="message"),
    # This task's action is to call the trigger's push method
    action=lambda ctx: email_trigger.push_exchange_xcom(
        ctx.session, ctx.input.message
    )
)

# Register the tasks in a group
trigger_group = cli.add_group(Group(name="trigger-example"))
trigger_group.add_task(email_trigger)
trigger_group.add_task(push_message)
```

**How to run this:**

1.  First, start the trigger in one terminal. It will run indefinitely, waiting for a message.
    ```sh
    $ zrb trigger-example email-trigger
    ```
2.  In a second terminal, push a message to the queue.
    ```sh
    $ zrb trigger-example push-message --message="Hello from Zrb"
    ```
3.  The first terminal will show the `email-sender` task being executed.
    ```
    Sending email with message: Hello from Zrb
    ```

## `Scheduler`: For Time-Based Automation

The `Scheduler` is a specialized `BaseTrigger` that runs tasks on a schedule, much like a traditional cron job.

It runs continuously, and at a specified time, it pushes the current timestamp to its `XCom` queue, which in turn triggers its `callback` tasks.

### Key Parameters

*   **`schedule`**: A cron-style pattern that defines when the task should run.
*   **`callback`**: The task or list of tasks to execute when the schedule matches.

| Cron Pattern | Description                                           |
|--------------|-------------------------------------------------------|
| `@yearly`    | Run once a year, i.e. `0 0 1 1 *`                       |
| `@annually`  | (Same as `@yearly`)                                   |
| `@monthly`   | Run once a month, i.e. `0 0 1 * *`                      |
| `@weekly`    | Run once a week, i.e. `0 0 * * 0`                       |
| `@daily`     | Run once a day, i.e. `0 0 * * *`                        |
| `@hourly`    | Run once an hour, i.e. `0 * * * *`                      |
| `@minutely`  | Run once a minute, i.e. `* * * * *`                     |
| `* * * * *`  | Standard 5-field cron pattern (minute, hour, day, etc.) |

### Example: A Daily Report

Here's how to set up a `Scheduler` to run a `generate-report` task every day at midnight.

```python
from zrb import cli, Group, CmdTask, Scheduler

# The task to be executed on schedule
generate_report = CmdTask(
    name="generate-report",
    cmd="echo 'Generating daily report...'"
)

# The scheduler task
daily_scheduler = Scheduler(
    name="daily-report-scheduler",
    description="Runs the daily report task at midnight",
    schedule="@daily",  # You can also use "0 0 * * *"
    callback=generate_report
)

# Register the scheduler in a group
schedule_group = cli.add_group(Group(name="schedule-example"))
schedule_group.add_task(daily_scheduler)
```

To start the scheduler, simply run its task. It will then run in the foreground, waiting for the schedule to match.

```sh
$ zrb schedule-example daily-report-scheduler
Monitoring cron pattern: @daily
Current time: 2023-10-27 10:30:00
...
```

By combining `BaseTrigger` and `Scheduler`, you can build sophisticated, event-driven, and time-based automations right within the Zrb framework.
