🔖 [Home](../../README.md) > [Documentation](../README.md) > [Core Concepts](./README.md)

# CLI and Group

At the very top of every Zrb project sits the `cli` object. It's the main entry point for all your tasks. Think of it as the root of a tree from which all other branches (groups and tasks) grow.

To make your tasks runnable from the command line, you must attach them to the `cli` object, either directly or by organizing them into `Group`s.

## Organizing with Groups

As your project grows, you'll want to organize your tasks. `Group`s are like folders for your tasks, allowing you to create a clean, nested hierarchy. You can add tasks to groups, and you can even put groups inside other groups.

This structure not only keeps your project tidy but also translates directly to how you call your tasks from the command line.

## Example

Let's see how this works in practice.

```python
from zrb import cli, Group, CmdTask

# Add a simple task directly to the cli
cli.add_task(CmdTask(name="hello", cmd="echo hello"))

# Create a group for alarm-related tasks
alarm_group = cli.add_group(Group(name="alarm"))

# Add a task to the "alarm" group
alarm_group.add_task(CmdTask(name="wake-up", cmd="echo 'Wake up!'"))

# Create a nested group for critical alarms
critical_group = alarm_group.add_group(Group(name="critical"))

# Add a task to the "critical" group
critical_group.add_task(CmdTask(name="fire", cmd="echo 'Fire!!!'"))
```

This setup creates the following command structure:

```
cli
├── [task] hello          (Run with: zrb hello)
└── [group] alarm
    ├── [task] wake-up      (Run with: zrb alarm wake-up)
    └── [group] critical
        └── [task] fire       (Run with: zrb alarm critical fire)
```

As you can see, the Python code maps intuitively to the command-line interface, making your automations easy to discover and use.