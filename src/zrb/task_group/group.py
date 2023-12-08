from zrb.helper.typing import List, Optional, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.helper.string.conversion import to_cli_name

# flake8: noqa E501
TGroup = TypeVar('TGroup', bound='Group')


@typechecked
class Group():
    '''
    Represents a group of tasks and subgroups, facilitating organization and hierarchy.

    This class allows the creation of a hierarchical structure by grouping tasks and 
    other task groups together. It provides methods to add tasks, retrieve tasks, 
    and generate Command-Line Interface (CLI) names based on group names.

    Attributes:
        name (str): The name of the group.
        description (Optional[str]): An optional description of the group.
        parent (Optional[TGroup]): The parent group of the current group, if any.

    Examples:
        >>> from zrb import Group
        >>> system_group = Group(name='system')
        >>> log_group = Group(name='log', parent='system')
    '''

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        parent: Optional[TGroup] = None
    ):
        self._name = name
        self._description = description
        self._parent = parent
        if parent is not None:
            parent._children.append(self)
        self._children: List[TGroup] = []
        self._tasks: List[AnyTask] = []

    def get_cli_name(self) -> str:
        '''
        Retrieves the CLI name of the group, formatted in kebab case.

        The method converts the group name into a CLI-friendly format, suitable for command-line usage.

        Returns:
            str: The CLI name of the group.

        Examples:
            >>> from zrb import Group
            >>> system_group = Group(name='my system')
            >>> print(system_group.get_cli_name())
            my-system
        '''
        return to_cli_name(self._name)

    def _get_full_cli_name(self) -> str:
        '''
        Retrieves the full CLI name of the group, including names of parent groups.

        This method is intended for internal use and constructs a full CLI name that reflects the group's hierarchy.

        Returns:
            str: The full CLI name of the group

        Examples:
            >>> from zrb import Group
            >>> system_group = Group(name='my system')
            >>> system_log_group = Group(name='log', parent=system_group)
            >>> print(system_log_group._get_full_cli_name())
            my-system log
        '''
        cli_name = self.get_cli_name()
        if self._parent is None:
            return cli_name
        parent_cli_name = self._parent._get_full_cli_name()
        return f'{parent_cli_name} {cli_name}'

    def _add_task(self, task: AnyTask):
        '''
        Adds a task to the group.

        This method is intended for internal use. It appends a given task to the  group's task list.

        Args:
            task (AnyTask): The task to be added.

        Examples:
            >>> from zrb import Group, Task
            >>> first_task = Task(name='first-task')
            >>> second_task = Task(name='second-task')
            >>> group = Group(name='group')
            >>> group._add_task(first_task)
            >>> group._add_task(second_task)
            >>> print(group.get_tasks())
            [<Task name=first-task>, <Task name=second-task>]
        '''
        self._tasks.append(task)

    def get_tasks(self) -> List[AnyTask]:
        '''
        Get direct Tasks under this Task Group.

        Returns:
            List[AnyTask]: List of direct Tasks under this Task Group.

        Examples:
            >>> from zrb import Group, Task
            >>> group = Group(name='group')
            >>> first_task = Task(name='first-task', group=group)
            >>> second_task = Task(name='second-task', group=group)
            >>> print(group.get_tasks())
            [<Task name=first-task>, <Task name=second-task>]
        '''
        return self._tasks

    def get_children(self) -> List[TGroup]:
        '''
        Retrieves the list of direct subgroups under this group.

        Returns a list of immediate subgroups nested within this group, helping to understand the group's hierarchical structure.

        Returns:
            List[Group]: List of direct subgroups under this Task group.

        Examples:
            >>> from zrb import Group, Task
            >>> group = Group(name='group')
            >>> sub_group_1 = TaskGroup(name='sub-group-1', parent=group)
            >>> sub_group_2 = TaskGroup(name='sub-group-2', parent=group)
            >>> print(group.get_children())
            [<Group name=sub-group-1>, <Group name=sub-group-2>]
        '''
        return self._children

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f'<{cls_name} name={self._name}>'
