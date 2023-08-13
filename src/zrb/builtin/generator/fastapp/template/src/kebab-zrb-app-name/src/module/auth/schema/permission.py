from typing import List
from core.schema import BaseDateTimeSchema, BaseCountSchema


class PermissionData(BaseDateTimeSchema):
    name: str
    description: str


class Permission(PermissionData):
    id: str

    class Config:
        orm_mode = True


class PermissionResult(BaseCountSchema):
    data: List[Permission]
