from typing import List
from core.schema import BaseDateTimeSchema, BaseCountSchema
from module.auth.schema.permission import Permission


class GroupBase(BaseDateTimeSchema):
    name: str
    description: str


class GroupData(GroupBase):
    permissions: List[str]


class Group(GroupBase):
    id: str
    permissions: List[Permission] = []

    class Config:
        orm_mode = True


class GroupResult(BaseCountSchema):
    data: List[Group]
