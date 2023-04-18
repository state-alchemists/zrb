from typing import List, Optional
from core.schema import BaseDateTimeSchema, BaseCountSchema
from module.auth.schema.permission import Permission
from module.auth.schema.group import Group


class UserBase(BaseDateTimeSchema):
    username: str
    phone: str
    email: str
    description: str
    groups: List[str]


class UserData(UserBase):
    password: str
    permissions: List[str]
    groups: List[str]


class User(UserBase):
    id: str
    permissions: List[Permission] = []
    groups: List[Group] = []
    hashed_password: Optional[str]

    class Config:
        orm_mode = True


class UserResult(BaseCountSchema):
    data: List[User]
