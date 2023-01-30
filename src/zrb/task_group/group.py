from typing import Optional, TypeVar
from pydantic import BaseModel
from ..helper.string.string import get_cmd_name

TGroup = TypeVar('TGroup', bound='Group')


class Group(BaseModel):
    name: str
    description: str = ''
    parent: Optional[TGroup] = None

    def get_cmd_name(self) -> str:
        return get_cmd_name(self.name)

    def get_id(self) -> str:
        group_id = self.get_cmd_name()
        if self.parent is None:
            return group_id
        parent_group_id = self.parent.get_id()
        return f'{parent_group_id} {group_id}'
