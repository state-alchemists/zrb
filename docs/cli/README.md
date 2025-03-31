# CLI

The `cli` module provides the command-line interface for Zrb. The `cli` object is an instance of the `Cli` class, which inherits from `Group`. This means that the `cli` object can contain tasks and subgroups, and it can be used to run tasks from the command line.

> **Important**: Only tasks that are registered to the CLI or its subgroups are accessible from the command line or web interface. Always make sure to add your tasks to the CLI or a group that is added to the CLI.

## Key Features

*   **Task Execution:** The `run` method is used to execute tasks from the command line.
*   **Group Management:** The `add_group` method is used to add subgroups to the CLI.
*   **Task Registration:** The `add_task` method or `@make_task` decorator is used to register tasks with the CLI.

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

## Usage

Tasks and groups are defined in Python code (typically in a `zrb_init.py` file). The Zrb runner will then execute the tasks and groups in the order specified by their dependencies. Tasks can be added to groups using the `add_task` method, and subgroups can be added to groups using the `add_group` method. Dependencies between tasks can be defined using the `>>` operator (e.g., `task1 >> task2` means that `task2` depends on `task1`). The `cli` object is used to register tasks and groups with the command-line interface, allowing them to be executed from the command line.

[Back to Documentation](../README.md)