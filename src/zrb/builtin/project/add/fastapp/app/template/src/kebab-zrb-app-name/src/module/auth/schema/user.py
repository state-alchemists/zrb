from component.schema import BaseCountSchema, BaseDateTimeSchema
from module.auth.schema.group import Group
from module.auth.schema.permission import Permission
from pydantic import BaseModel


class UserBase(BaseDateTimeSchema):
    username: str
    phone: str
    email: str
    description: str
    groups: list[str]
    permissions: list[str]


class UserData(UserBase):
    password: str


class User(UserBase):
    id: str
    permissions: list[Permission] = []
    groups: list[Group] = []

    class Config:
        from_attributes = True


class UserResult(BaseCountSchema):
    data: list[User]


class UserLogin(BaseModel):
    identity: str
    password: str
