🔖 [Documentation Home](../README.md)
# Group

A Group is a collection of tasks and subgroups that are organized together. Groups provide a way to structure and manage complex workflows. Groups are defined by inheriting from `AnyGroup` (or directly using the `Group` class).

> **Important**: Groups must be registered with the CLI (or a parent group that is registered with the CLI) for their tasks to be accessible from the command line or web interface.

## Key Features

Groups have the following key properties:

*   **Name:** A unique identifier for the group (`name` property). Used to reference the group from the CLI or other groups.
*   **Description:** A human-readable explanation of the group's purpose (`description` property). Displayed in the CLI and web interface.
*   **Subtasks:** A dictionary of tasks that belong to the group (`subtasks` property). You can add tasks using the `add_task()` method.
*   **Subgroups:** A dictionary of subgroups that belong to the group (`subgroups` property). You can add subgroups using the `add_group()` method.

## Example

```python
from zrb import Group, Task, CmdTask, cli

# Define a group
my_group = Group(
    name="my_group",
    description="This is an example group.",
)
cli.add_group(my_group)  # Register the group with CLI

# Add tasks to the group
task1 = CmdTask(name="task1", cmd="echo 'Task 1'")
task2 = CmdTask(name="task2", cmd="echo 'Task 2'")
my_group.add_task(task1)
my_group.add_task(task2)

# Create a subgroup
my_subgroup = Group(
    name="my_subgroup",
    description="This is an example subgroup."
)
my_group.add_group(my_subgroup)  # Add subgroup to parent group

# Add a task to the subgroup
task3 = CmdTask(name="task3", cmd="echo 'Task 3'")
my_subgroup.add_task(task3)
```

[Back to Documentation](../README.md)