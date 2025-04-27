🔖 [Documentation Home](../README.md)
# CLI

The `cli` module provides the command-line interface for Zrb. The `cli` object is an instance of the `Cli` class, which inherits from `Group`. This means that the `cli` object can contain tasks and subgroups, and it can be used to run tasks from the command line.

> **Important**: Only tasks that are registered to the CLI or its subgroups are accessible from the command line or web interface. Always make sure to add your tasks to the CLI or a group that is added to the CLI.

## Key Features

The `cli` object provides the following key functionalities:

*   **Task Execution:** The `run` method is used to execute tasks from the command line. This is the entry point for running your defined tasks.
*   **Group Management:** The `add_group` method is used to add subgroups to the CLI. This allows you to organize tasks hierarchically.
*   **Task Registration:** The `add_task` method or `@make_task` decorator is used to register tasks with the CLI. This makes your tasks discoverable and executable.

## Example

```python
from zrb import cli, Task, CmdTask, Group, make_task

# Define a task and register it with CLI
@cli.add_task
class MyTask(Task):
    name = "my_task"
    description = "This is an example task that is registered with the CLI."
    def run(self, ctx):
        print("Hello, world!")

# Or using the @make_task decorator
@make_task(
    name="my_other_task", 
    description="This is another example task", 
    group=cli
)
def my_other_task(ctx):
    print("Hello from another task!")

# Create a group and register it with CLI
my_group = Group(
    name="my_group",
    description="This is an example group."
)
cli.add_group(my_group)

# Add a task to the group
my_group.add_task(
    CmdTask(
        name="group_task",
        description="This task belongs to my_group",
        cmd="echo 'Hello from my_group!'"
    )
)
```

## Task Accessibility

To make a task accessible from the command line or web interface, it must be registered with the CLI or a group that is registered with the CLI. Here are the ways to register tasks:

1. **Direct registration with CLI**:
   ```python
   cli.add_task(my_task)
   ```

2. **Using the `@make_task` decorator with `group=cli`**:
   ```python
   @make_task(name="my_task", group=cli)
   def my_task(ctx):
       # Task implementation
   ```

3. **Adding to a group that is registered with CLI**:
   ```python
   my_group = Group("my_group")
   cli.add_group(my_group)
   my_group.add_task(my_task)
   ```

[Back to Documentation](../README.md)