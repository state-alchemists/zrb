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

## Schedule Syntax (Crontab)

The `Scheduler` accepts standard cron expressions or preset keywords.

### Preset Keywords

| Keyword | Meaning | Cron Equivalent |
|---------|---------|-----------------|
| `@minutely` | Every minute | `* * * * *` |
| `@hourly` | Every hour | `0 * * * *` |
| `@daily` | Every day at midnight | `0 0 * * *` |
| `@weekly` | Every Sunday at midnight | `0 0 * * 0` |
| `@monthly` | 1st of month at midnight | `0 0 1 * *` |

### Standard Cron Format

```python
Scheduler(
    name="custom-schedule",
    schedule="*/15 * * * *",  # Every 15 minutes
    ...
)
```

The five fields are:

```
┌───────── minute (0-59)
│ ┌──────── hour (0-23)
│ │ ┌─────── day of month (1-31)
│ │ │ ┌────── month (1-12)
│ │ │ │ ┌───── day of week (0-6, 0=Sunday)
│ │ │ │ │
* * * * *
```

### Cron Operators

| Operator | Example | Meaning |
|----------|---------|---------|
| `*` | `* * * * *` | Every unit |
| `,` | `1,15 * * * *` | Minutes 1 and 15 |
| `-` | `9-17 * * * *` | Range (9 AM to 5 PM) |
| `/` | `*/5 * * * *` | Step (every 5 minutes) |
| Combined | `0 9-17/2 * * 1-5` | Every 2 hours from 9-5, weekdays |

### Real-World Examples

```python
# Weekdays at 9 AM
Scheduler(name="daily-report", schedule="0 9 * * 1-5", ...)

# Every 30 minutes during business hours
Scheduler(name="health-check", schedule="*/30 9-18 * * *", ...)

# First day of every quarter
Scheduler(name="quarterly", schedule="0 0 1 1,4,7,10 *", ...)

# Every Monday at 8:30 AM
Scheduler(name="weekly-standup", schedule="30 8 * * 1", ...)
```

---

## Advanced Trigger Patterns

### Trigger with Retry Logic

Add retry to the trigger itself when the listening action may temporarily fail:

```python
file_watcher = cli.add_task(
    BaseTrigger(
        name="robust-watcher",
        action=watch_file,
        callback=my_callback,
        retries=3,
        retry_period=5.0,
    )
)
```

### Multiple Callbacks on One Trigger

Chain multiple tasks from a single trigger using `successor` on the callback's task:

```python
notify = CmdTask(name="notify", cmd="echo 'Event detected!'")
process = CmdTask(name="process", cmd="echo 'Processing...'", successor=[notify])

my_callback = Callback(
    task=process,
    input_mapping={"file": "{ctx.xcom.event_queue.pop()}"}
)
```

### Scheduler with Conditional Execution

```python
daily_backup = cli.add_task(
    Scheduler(
        name="backup-scheduler",
        schedule="@daily",
        queue_name="backup_queue",
        callback=Callback(
            task=CmdTask(
                name="run-backup",
                execute_condition=lambda ctx: ctx.env.ENABLE_BACKUP == "true",
                cmd="echo 'Running backup at {ctx.xcom.backup_queue.pop()}'",
            ),
            input_mapping={"timestamp": "{ctx.xcom.backup_queue.pop()}"}
        )
    )
)
```

---

## Daemon Lifecycle

Both `BaseTrigger` and `Scheduler` run as foreground daemon processes. To stop them:

- Press `Ctrl+C` to send `SIGINT`
- Set up a system service (systemd, launchd) for background execution
- Use a readiness check on the daemon to confirm it's listening before proceeding

---

🔖 [Documentation Home](../../README.md) > [Task Types](./) > Triggers & Schedulers
