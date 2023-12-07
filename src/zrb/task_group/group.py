from zrb.helper.typing import List, Optional, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.helper.string.conversion import to_cli_name

TGroup = TypeVar('TGroup', bound='Group')


@typechecked
class Group():
    '''
    Task Group to help you organize your Tasks.

    A Task Group might contains:
    - Tasks.
    - Other Task Groups.

    Attributes:
        name (str): Group name.
        description (Optional[str]): Description of the group.
        parent (Optional[Group]): Parent of current group
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
        Get group CLI name (i.e., in kebab case).

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
        cli_name = self.get_cli_name()
        if self._parent is None:
            return cli_name
        parent_cli_name = self._parent._get_full_cli_name()
        return f'{parent_cli_name} {cli_name}'

    def _add_task(self, task: AnyTask):
        self._tasks.append(task)

    def get_tasks(self) -> List[AnyTask]:
        '''
        Get tasks under this group.

        Returns:
            List[AnyTask]: List of tasks under this group.

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
        Get groups under this group.

        Returns:
            List[Group]: List of groups under this group.

        Examples:
            >>> from zrb import Group, Task
            >>> group = Group(name='group')
            >>> sub_group_1 = TaskGroup(name='sub-group-1', parent=group)
            >>> sub_group_2 = TaskGroup(name='sub-group-2', parent=group)
            >>> group.get_children()
            [<Group name=sub-group-1>, <Group name=sub-group-2>]
        '''
        return self._children

    def __repr__(self) -> str:
        return f'<Group name={self._name}>'
