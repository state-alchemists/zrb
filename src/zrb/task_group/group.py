from zrb.helper.typing import List, Optional, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.helper.string.conversion import to_cmd_name

TGroup = TypeVar('TGroup', bound='Group')


@typechecked
class Group():
    '''
    Task Group.

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

    def get_cmd_name(self) -> str:
        return to_cmd_name(self._name)

    def _get_full_cmd_name(self) -> str:
        cmd_name = self.get_cmd_name()
        if self._parent is None:
            return cmd_name
        parent_cmd_name = self._parent._get_full_cmd_name()
        return f'{parent_cmd_name} {cmd_name}'

    def get_id(self) -> str:
        '''
        Get this group id.

        Returns:
            str: Group id

        Examples:
            >>> parent_group = Group(name='parent-group')
            >>> group = Group(name='group', parent=parent_group)
            >>> group.get_id()
            'parent-group group'
        '''
        group_id = self.get_cmd_name()
        if self._parent is None:
            return group_id
        parent_group_id = self._parent.get_id()
        return f'{parent_group_id} {group_id}'

    def add_task(self, task: AnyTask):
        '''
        Add task to this group.

        Args:
            task (AnyTask): Task to be added.

        Returns:
            None

        Examples:
            >>> group = Group(name='group')
            >>> task = Task(name='task')
            >>> group.add_task(task)
        '''
        self._tasks.append(task)

    def get_tasks(self) -> List[AnyTask]:
        '''
        Get tasks under this group.

        Returns:
            List[AnyTask]: List of tasks under this group

        Examples:
            >>> group = Group(name='group')
            >>> first_task = Task(name='first-task', group=group)
            >>> second_task = Task(name='second-task')
            >>> group.get_tasks()
            [<Task name=first-task>, <Task name=second-task>]
        '''
        return self._tasks

    def get_children(self) -> List[TGroup]:
        '''
        Get groups under this group.

        Returns:
            List[Group]: List of groups under this group

        Examples:
            >>> group = Group(name='group')
            >>> sub_group_1 = TaskGroup(name='sub-group-1', parent=group)
            >>> sub_group_2 = TaskGroup(name='sub-group-2', parent=group)
            >>> group.get_children()
            [<Group name=sub-group-1>, <Group name=sub-group-2>]
        '''
        return self._children

    def __repr__(self) -> str:
        return f'<Group name={self._name}>'
