🔖 [Table of Contents](../README.md)

# Task Group

<!--start-doc-->
## `Group`

Represents a group of tasks and subgroups, facilitating organization and hierarchy.

This class allows the creation of a hierarchical structure by grouping tasks and
other task groups together. It provides methods to add tasks, retrieve tasks,
and generate Command-Line Interface (CLI) names based on group names.

__Attributes:__

- `name` (`str`): The name of the group.
- `description` (`Optional[str]`): An optional description of the group.
- `parent` (`Optional[TGroup]`): The parent group of the current group, if any.

__Examples:__

```python
from zrb import Group
system_group = Group(name='system')
log_group = Group(name='log', parent='system')
```


### `Group._add_task`

Adds a task to the group.

This method is intended for internal use. It appends a given task to the  group's task list.

__Arguments:__

- `task` (`AnyTask`): The task to be added.

__Examples:__

```python
from zrb import Group, Task
first_task = Task(name='first-task')
second_task = Task(name='second-task')
group = Group(name='group')
group._add_task(first_task)
group._add_task(second_task)
print(group.get_tasks())
```

```
[<Task "group first-task">, <Task "group second-task">]
```


### `Group._get_full_cli_name`

Retrieves the full CLI name of the group, including names of parent groups.

This method is intended for internal use and constructs a full CLI name that reflects the group's hierarchy.

__Returns:__

`str`: The full CLI name of the group

__Examples:__

```python
from zrb import Group
system_group = Group(name='my system')
system_log_group = Group(name='log', parent=system_group)
print(system_log_group._get_full_cli_name())
```

```
my-system log
```


### `Group.get_children`

Retrieves the list of direct subgroups under this group.

Returns a list of immediate subgroups nested within this group, helping to understand the group's hierarchical structure.

__Returns:__

`List[Group]`: List of direct subgroups under this Task group.

__Examples:__

```python
from zrb import Group, Task
group = Group(name='group')
sub_group_1 = TaskGroup(name='sub-group-1', parent=group)
sub_group_2 = TaskGroup(name='sub-group-2', parent=group)
print(group.get_children())
```

```
[<Group "group sub-group-1">, <Group "group sub-group-2">]
```


### `Group.get_cli_name`

Retrieves the CLI name of the group, formatted in kebab case.

The method converts the group name into a CLI-friendly format, suitable for command-line usage.

__Returns:__

`str`: The CLI name of the group.

__Examples:__

```python
from zrb import Group
system_group = Group(name='my system')
print(system_group.get_cli_name())
```

```
my-system
```


### `Group.get_description`

Retrieves group description.

__Returns:__

`str`: Description of the group.

__Examples:__

```python
from zrb import Group
group = Group(name='group', description='description of the group')
print(group.get_description())
```

```
description of the group
```


### `Group.get_parent`

Retrieves parent of the Group.

__Returns:__

`Optional[Group]`: Parent of the group.

__Examples:__

```python
from zrb import Group
system_group = Group(name='my system')
system_log_group = Group(name='log', parent=system_group)
print(system_group.get_parent())
print(system_log_group.get_parent())
```

```
None
<Group "my-system">
```


### `Group.get_tasks`

Get direct Tasks under this Task Group.

__Returns:__

`List[AnyTask]`: List of direct Tasks under this Task Group.

__Examples:__

```python
from zrb import Group, Task
group = Group(name='group')
first_task = Task(name='first-task', group=group)
second_task = Task(name='second-task', group=group)
print(group.get_tasks())
```

```
[<Task "group first-task">, <Task "group second-task">]
```


<!--end-doc-->

🔖 [Table of Contents](../README.md)
