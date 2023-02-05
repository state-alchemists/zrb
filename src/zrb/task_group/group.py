from typing import Optional, TypeVar
from typeguard import typechecked
from ..helper.string.conversion import to_cmd_name

TGroup = TypeVar('TGroup', bound='Group')


@typechecked
class Group():

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        parent: Optional[TGroup] = None
    ):
        self.name = name
        self.description = description
        self.parent = parent

    def get_cmd_name(self) -> str:
        return to_cmd_name(self.name)

    def get_complete_name(self) -> str:
        cmd_name = self.get_cmd_name()
        if self.parent is None:
            return cmd_name
        parent_cmd_name = self.parent.get_complete_name()
        return f'{parent_cmd_name} {cmd_name}'

    def get_id(self) -> str:
        group_id = self.get_cmd_name()
        if self.parent is None:
            return group_id
        parent_group_id = self.parent.get_id()
        return f'{parent_group_id} {group_id}'
