🔖 [Home](../../../../../README.md) > [Documentation](../../../../README.md) > [Core Concepts](../../../README.md) > [Task](../../README.md) > [Types](../README.md)

# Trigger and Scheduler

While most tasks run once and then complete, Zrb also supports long-running tasks that can react to events or run on a schedule. These are built on two key components: the `BaseTrigger` and the `Scheduler`.

These components work by using a `Callback` object to wrap the task that should be executed when an event occurs.

## The `Callback` Wrapper

A `Callback` is an essential adapter that connects a trigger's event to a task's execution. You don't use a `Task` directly as a callback; you wrap it in a `Callback` object first.

The `Callback` class is responsible for:
1.  **Wrapping a Task**: It holds a reference to the task that should be run.
2.  **Mapping Inputs**: It uses an `input_mapping` dictionary to take data from the trigger's event and pass it to the inputs of the wrapped task.

## `BaseTrigger`: For Event-Driven Tasks

A `BaseTrigger` is a special type of task designed to be a long-running process that listens for events and triggers `callback`s in response.

### How It Works

1.  **Define a Long-Running `action`**: The core of a `BaseTrigger` is its `action`. This is a long-running Python function you provide that listens for an event (e.g., watching a file, polling an API).
2.  **Push to XCom Queue**: When the event occurs, the `action` pushes data to the trigger's own `XCom` queue using `ctx.task.push_exchange_xcom(ctx.session, data)`. The `ctx.task` refers to the trigger instance itself.
3.  **Trigger `Callback`**: This push automatically executes the `Callback` object(s) defined in the `callback` parameter. The `Callback` then uses its `input_mapping` to retrieve the data from the XCom queue and runs its wrapped task.

### Example: A File Watcher

Here is a correct implementation of a trigger that watches a file for changes.

```python
import asyncio
import os
from zrb import cli, Group, CmdTask, BaseTrigger, StrInput, AnyContext, Callback

# 1. The task that will be executed by the callback
process_file_content = CmdTask(
    name="process-file-content",
    input=StrInput(name="content", help="The content of the file"),
    cmd='echo "File content processed: {ctx.input.content}"'
)

# 2. The long-running action for the trigger
async def watch_file_action(ctx: AnyContext):
    file_path = ctx.input.file_path
    ctx.print(f"Watching file: {file_path}")
    
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("initial content")

    with open(file_path, "r") as f:
        last_content = f.read()
    ctx.print(f"Initial content: {last_content}")

    while True:
        await asyncio.sleep(2)
        with open(file_path, "r") as f:
            current_content = f.read()
        
        if current_content != last_content:
            ctx.print("Content changed, triggering callback...")
            # The action pushes to its own trigger's queue
            ctx.task.push_exchange_xcom(ctx.session, current_content)
            last_content = current_content

# 3. The trigger task definition
file_watcher = BaseTrigger(
    name="file-watcher",
    description="Watches content.txt for changes",
    input=StrInput(name="file_path", default="content.txt"),
    queue_name="file_updates",
    action=watch_file_action,
    # Wrap the task in a Callback and map the inputs
    callback=Callback(
        task=process_file_content,
        input_mapping={"content": "{ctx.xcom.file_updates.pop()}"}
    )
)

# A helper task to test the trigger
update_file = CmdTask(
    name="update-file",
    input=StrInput(name="content", default="new content"),
    cmd='echo "{ctx.input.content}" > content.txt'
)

watch_group = cli.add_group(Group(name="watch-example"))
watch_group.add_task(file_watcher)
watch_group.add_task(update_file)
```

**How to run this:**
1.  In one terminal, start the `file-watcher`. It will run forever.
    ```sh
    $ zrb watch-example file-watcher
    ```
2.  In a second terminal, change the file's content.
    ```sh
    $ zrb watch-example update-file --content="hello world"
    ```
3.  The first terminal detects the change and the `Callback` executes `process-file-content`.
    ```
    Content changed, triggering callback...
    File content processed: hello world
    ```

## `Scheduler`: For Time-Based Automation

The `Scheduler` is a specialized `BaseTrigger` with a built-in `action` that loops and checks the time. When the `schedule` matches the current time, it pushes the timestamp to its `XCom` queue, triggering its `callback`.

You must wrap the callback task in a `Callback` object, just like with `BaseTrigger`.

### Example: A Daily Report

Here is a corrected example of a `Scheduler`.

```python
from zrb import cli, Group, CmdTask, Scheduler, Callback

# The task to be executed on schedule
generate_report = CmdTask(
    name="generate-report",
    input=StrInput(name="timestamp"),
    cmd="echo 'Generating daily report for timestamp: {ctx.input.timestamp}'"
)

# The scheduler task
daily_scheduler = Scheduler(
    name="daily-report-scheduler",
    description="Runs the daily report task at midnight",
    schedule="@minutely",  # Using @minutely for easy testing
    queue_name="report_schedule",
    callback=Callback(
        task=generate_report,
        input_mapping={"timestamp": "{ctx.xcom.report_schedule.pop()}"}
    )
)

schedule_group = cli.add_group(Group(name="schedule-example"))
schedule_group.add_task(daily_scheduler)
```

To start the scheduler, run its task. It will run in the foreground, and every minute, it will trigger the `generate-report` task.
```sh
$ zrb schedule-example daily-report-scheduler
Monitoring cron pattern: @minutely
...
```

By combining `BaseTrigger` and `Scheduler`, you can build sophisticated, event-driven, and time-based automations right within the Zrb framework.
