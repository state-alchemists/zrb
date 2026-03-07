🔖 [Documentation Home](../../README.md) > [Task Types](./) > Triggers & Schedulers

# Triggers and Schedulers

While most tasks run once and exit, Zrb supports long-running daemon tasks that react to events or time schedules. These are built using the `BaseTrigger` and `Scheduler` classes, combined with the `Callback` wrapper.

---

## Table of Contents

- [The `Callback` Wrapper](#the-callback-wrapper)
- [`BaseTrigger` (Event-Driven)](#1-basetrigger-event-driven)
- [`Scheduler` (Time-Driven)](#2-scheduler-time-driven)
- [Quick Comparison](#quick-comparison)

---

## The `Callback` Wrapper

To connect an event to a task execution, you must wrap the target task in a `Callback` object. The `Callback` maps data emitted by the trigger into the inputs of the target task.

```python
from zrb import Callback, CmdTask, StrInput

# The task to run
print_event = CmdTask(
    name="print-event", 
    input=StrInput(name="message"),
    cmd="echo 'Event received: {ctx.input.message}'"
)

# The wrapper
my_callback = Callback(
    task=print_event,
    # Map the XCom data from the trigger queue to the 'message' input
    input_mapping={"message": "{ctx.xcom.event_queue.pop()}"}
)
```

| Callback Parameter | Description |
|-------------------|-------------|
| `task` | The task to execute when triggered |
| `input_mapping` | Map XCom data to task inputs |

---

## 1. `BaseTrigger` (Event-Driven)

A `BaseTrigger` is a daemon task that loops forever, listening for events (like file changes, webhook receives, etc.). When an event occurs, it pushes data to its `XCom` queue, which automatically fires its `callback`.

### When to Use

| Use Case | Example |
|----------|---------|
| File watching | React to file changes |
| Webhooks | Handle incoming webhook events |
| Message queues | Listen to RabbitMQ, Redis pub/sub |
| Custom events | Any event source |

### Example: A File Watcher

```python
import asyncio
from zrb import cli, BaseTrigger, StrInput

# 1. The long-running listener function
async def watch_file(ctx):
    file_path = ctx.input.file_path
    
    # Read initial state
    with open(file_path, "r") as f:
        last_content = f.read()

    # Infinite loop checking for changes
    while True:
        await asyncio.sleep(2)
        with open(file_path, "r") as f:
            current_content = f.read()
        
        if current_content != last_content:
            ctx.print("File changed!")
            # Push the new content to the trigger's XCom queue!
            # This action automatically fires the Callback.
            ctx.task.push_exchange_xcom(ctx.session, current_content)
            last_content = current_content

# 2. Define the Trigger Task
file_watcher = cli.add_task(
    BaseTrigger(
        name="file-watcher",
        input=StrInput(name="file_path", default="data.txt"),
        queue_name="event_queue",  # The XCom queue name
        action=watch_file,
        callback=my_callback      # The callback defined above
    )
)
```

When you run `zrb file-watcher`, it will run continuously. Every time `data.txt` is modified, the `print_event` task will execute.

---

## 2. `Scheduler` (Time-Driven)

The `Scheduler` is a specialized trigger with a built-in time loop. It acts like a Cron daemon. When the schedule matches, it pushes the current timestamp to its XCom queue and fires its callback.

### When to Use

| Use Case | Example |
|----------|---------|
| Periodic reports | Daily/weekly report generation |
| Scheduled maintenance | Cleanup tasks |
| Polling | Check external services periodically |

### Example: A Daily Cron Job

```python
from zrb import cli, CmdTask, Scheduler, Callback

# The job to run
generate_report = CmdTask(
    name="generate-report",
    input=StrInput(name="timestamp"),
    cmd="echo 'Generating report for: {ctx.input.timestamp}'"
)

# The Scheduler daemon
daily_scheduler = cli.add_task(
    Scheduler(
        name="daily-report-scheduler",
        schedule="@minutely",  # Cron syntax or presets
        queue_name="cron_queue",
        callback=Callback(
            task=generate_report,
            input_mapping={"timestamp": "{ctx.xcom.cron_queue.pop()}"}
        )
    )
)
```

When you run `zrb daily-report-scheduler`, the process remains alive in the foreground, executing the `generate_report` task every minute.

### Schedule Presets

| Preset | Equivalent Cron |
|--------|-----------------|
| `@minutely` | `* * * * *` |
| `@hourly` | `0 * * * *` |
| `@daily` | `0 0 * * *` |
| `@weekly` | `0 0 * * 0` |
| `@monthly` | `0 0 1 * *` |

---

## Quick Comparison

| Feature | `BaseTrigger` | `Scheduler` |
|---------|---------------|-------------|
| **Trigger** | Events (file, webhook, etc.) | Time (cron) |
| **Runs forever** | Yes | Yes |
| **XCom push** | Manual | Automatic (timestamp) |
| **Use case** | Reactive automation | Scheduled automation |

---