from typing import List
from core.schema import BaseDateTimeSchema, BaseCountSchema


class PermissionData(BaseDateTimeSchema):
    name: str
    description: str


class Permission(PermissionData):
    id: str

    class Config:
        orm_mode = True
        from_attributes = True


class PermissionResult(BaseCountSchema):
    data: List[Permission]
