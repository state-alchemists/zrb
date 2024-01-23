from typing import List

from core.schema import BaseCountSchema, BaseDateTimeSchema
from module.auth.schema.permission import Permission


class GroupBase(BaseDateTimeSchema):
    name: str
    description: str


class GroupData(GroupBase):
    permissions: List[str]


class Group(GroupBase):
    class Config:
        orm_mode = True
        from_attributes = True

    id: str
    permissions: List[Permission] = []


class GroupResult(BaseCountSchema):
    data: List[Group]
