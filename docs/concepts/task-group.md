🔖 [Table of Contents](../README.md)

# Task Group

<!--start-doc-->
## `Group`

Task Group that help you organize your Tasks.

A Task Group might contains:
- Tasks.
- Other Task Groups.

__Attributes:__

- `name` (`str`): Group name.
- `description` (`Optional[str]`): Description of the group.
- `parent` (`Optional[Group]`): Parent of current group

__Examples:__

```python
from zrb import Group
system_group = Group(name='system')
log_group = Group(name='log', parent='system')
```


### `Group._add_task`

Add Task to Task Group

This method is meant for internal use.

__Arguments:__

- `task` (`AnyTask`): Task to be added.

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
[<Task name=first-task>, <Task name=second-task>]
```


### `Group._get_full_cli_name`

Get Task Group's full CLI name

This method is meant for internal use.

__Returns:__

`str`: Group full CLI name.

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

Get direct Sub Task Groups under this Task Group.

__Returns:__

`List[Group]`: List of direct Sub Task Groups under this Task Group.

__Examples:__

```python
from zrb import Group, Task
group = Group(name='group')
sub_group_1 = TaskGroup(name='sub-group-1', parent=group)
sub_group_2 = TaskGroup(name='sub-group-2', parent=group)
print(group.get_children())
```

```
[<Group name=sub-group-1>, <Group name=sub-group-2>]
```


### `Group.get_cli_name`

Get Task Group's CLI name (i.e., in kebab case).

__Returns:__

`str`: Group CLI name.

__Examples:__

```python
from zrb import Group
system_group = Group(name='my system')
print(system_group.get_cli_name())
```

```
my-system
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
[<Task name=first-task>, <Task name=second-task>]
```


<!--end-doc-->

🔖 [Table of Contents](../README.md)
