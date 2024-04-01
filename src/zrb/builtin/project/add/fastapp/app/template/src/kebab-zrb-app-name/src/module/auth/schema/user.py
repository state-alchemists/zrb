from typing import List

from component.schema import BaseCountSchema, BaseDateTimeSchema
from module.auth.schema.group import Group
from module.auth.schema.permission import Permission
from pydantic import BaseModel


class UserBase(BaseDateTimeSchema):
    username: str
    phone: str
    email: str
    description: str
    groups: List[str]
    permissions: List[str]


class UserData(UserBase):
    password: str


class User(UserBase):
    id: str
    permissions: List[Permission] = []
    groups: List[Group] = []

    class Config:
        from_attributes = True


class UserResult(BaseCountSchema):
    data: List[User]


class UserLogin(BaseModel):
    identity: str
    password: str
