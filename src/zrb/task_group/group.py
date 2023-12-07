from zrb.helper.typing import List, Optional, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.helper.string.conversion import to_cli_name

TGroup = TypeVar('TGroup', bound='Group')


@typechecked
class Group():
    '''
    Task Group that help you organize your Tasks.

    A Task Group might contains:
    - Tasks.
    - Other Task Groups.

    Attributes:
        name (str): Group name.
        description (Optional[str]): Description of the group.
        parent (Optional[Group]): Parent of current group

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
        Get Task Group's CLI name (i.e., in kebab case).

        Returns:
            str: Group CLI name.

        Examples:
            >>> from zrb import Group
            >>> system_group = Group(name='my system')
            >>> print(system_group.get_cli_name())
            my-system
        '''
        return to_cli_name(self._name)

    def _get_full_cli_name(self) -> str:
        '''
        Get Task Group's full CLI name

        This method is meant for internal use.

        Returns:
            str: Group full CLI name.

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
        Add Task to Task Group

        This method is meant for internal use.

        Args:
            task (AnyTask): Task to be added.

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
        Get direct Sub Task Groups under this Task Group.

        Returns:
            List[Group]: List of direct Sub Task Groups under this Task Group.

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
