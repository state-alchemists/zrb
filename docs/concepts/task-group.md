🔖 [Table of Contents](../README.md)

# Task Group

<!--start-doc-->
## `Group`
Task Group to help you organize your Tasks.

A Task Group might contains:
- Tasks.
- Other Task Groups.

__Attributes:__

- `name` (`str`): Group name.
- `description` (`Optional[str]`): Description of the group.
- `parent` (`Optional[Group]`): Parent of current group

### `Group.__init__`
No documentation available.

### `Group.__repr__`
No documentation available.

### `Group._add_task`
No documentation available.

### `Group._get_full_cli_name`
No documentation available.

### `Group.get_children`
Get groups under this group.

__Returns:__

`List[Group]`: List of groups under this group.

__Examples:__

```python
from zrb import Group, Task
group = Group(name='group')
sub_group_1 = TaskGroup(name='sub-group-1', parent=group)
sub_group_2 = TaskGroup(name='sub-group-2', parent=group)
group.get_children()
```

```
[<Group name=sub-group-1>, <Group name=sub-group-2>]
```

### `Group.get_cli_name`
Get group CLI name (i.e., in kebab case).

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
Get tasks under this group.

__Returns:__

`List[AnyTask]`: List of tasks under this group.

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
