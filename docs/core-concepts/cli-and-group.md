🔖 [Home](../../README.md) > [Documentation](../README.md) > [Core Concepts](./README.md)

# CLI and Group

Task access hierarchy always starts with a `cli`.

You can add `groups` or `tasks` to the `cli`.

You can also add `groups` inside existing `groups`.

But you have to make sure that everything starts with a `cli`. Otherwise, your `tasks` or `groups` won't be accessible.

```python
from zrb import cli, Group, CmdTask

# make and register "hello", task to the cli. 
cli.add_task(CmdTask(name="hello", cmd="echo hello"))

# make and register "alarm" group to the cli.
alarm_group = cli.add_group(Group(name="alarm"))
# make and register "wake-up" task to the "alarm" group.
alarm_group.add_task(CmdTask(name="wake-up", cmd="echo wake up!"))

# make and register "critical" group to the "alarm" group.
alarm_critical_group = alarm_group.add_group(Group(name="critical"))
# make and register "fire" task to the "critical" group.
alarm_critical_group.add_task(CmdTask(name="fire", cmd="echo fire!!!"))
```

The mental model hierarchy will be:

```
cli
  [task] hello          zrb hello
  [group] alarm
    [task] wake-up      zrb alarm wake-up
    [group] critical
      [task] fire       zrb alarm critical fire