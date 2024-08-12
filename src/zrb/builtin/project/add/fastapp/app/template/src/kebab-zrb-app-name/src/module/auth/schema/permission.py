from component.schema import BaseCountSchema, BaseDateTimeSchema


class PermissionData(BaseDateTimeSchema):
    name: str
    description: str


class Permission(PermissionData):
    id: str

    class Config:
        from_attributes = True


class PermissionResult(BaseCountSchema):
    data: list[Permission]
