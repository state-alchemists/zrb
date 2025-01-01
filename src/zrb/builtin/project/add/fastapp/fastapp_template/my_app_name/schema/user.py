import datetime

import ulid
from my_app_name.schema.permission import Permission
from my_app_name.schema.role import Role
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    username: str


class UserCreate(UserBase):
    password: str
    roles: list[str] | None = None

    def with_audit(self, created_by: str) -> "UserCreateWithAudit":
        return UserCreateWithAudit(**self.model_dump(), created_by=created_by)


class UserCreateWithAudit(UserCreate):
    created_by: str


class UserUpdate(SQLModel):
    username: str | None = None
    password: str | None = None

    def with_audit(self, updated_by: str) -> "UserUpdateWithAudit":
        return UserUpdateWithAudit(**self.model_dump(), updated_by=updated_by)


class UserUpdateWithAudit(UserUpdate):
    updated_by: str


class UserResponse(UserBase):
    id: str
    roles: list[Role]
    permissions: list[Permission]


class MultipleUserResponse(BaseModel):
    data: list[UserResponse]
    count: int


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime = Field(index=True)
    created_by: str = Field(index=True)
    updated_at: datetime.datetime | None = Field(index=True)
    updated_by: str | None = Field(index=True)
    username: str = Field(index=True)
    password: str


class UserRole(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    user_id: str = Field(index=True)
    role_id: str = Field(index=True)
    created_at: datetime.datetime | None
    created_by: str | None
