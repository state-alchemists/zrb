from zrb.helper.typing import List, Optional, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.helper.string.conversion import to_cmd_name

TGroup = TypeVar('TGroup', bound='Group')


@typechecked
class Group():
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

    def get_complete_name(self) -> str:
        cmd_name = self.get_cmd_name()
        if self._parent is None:
            return cmd_name
        parent_cmd_name = self._parent.get_complete_name()
        return f'{parent_cmd_name} {cmd_name}'

    def get_id(self) -> str:
        group_id = self.get_cmd_name()
        if self._parent is None:
            return group_id
        parent_group_id = self._parent.get_id()
        return f'{parent_group_id} {group_id}'

    def add_task(self, task: AnyTask):
        self._tasks.append(task)

    def get_tasks(self) -> List[AnyTask]:
        return self._tasks

    def get_children(self) -> List[TGroup]:
        return self._children
