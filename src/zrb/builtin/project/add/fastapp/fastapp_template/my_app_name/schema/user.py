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

    def with_audit(self, created_by: str) -> "UserCreateWithAudit":
        return UserCreateWithAudit(**self.model_dump(), created_by=created_by)


class UserCreateWithAudit(UserCreate):
    created_by: str


class UserCreateWithRoles(UserCreate):
    role_ids: list[str] | None = None

    def with_audit(self, created_by: str) -> "UserCreateWithRolesAndAudit":
        return UserCreateWithRolesAndAudit(**self.model_dump(), created_by=created_by)


class UserCreateWithRolesAndAudit(UserCreateWithRoles):
    created_by: str

    def get_user_create_with_audit(self) -> UserCreateWithAudit:
        data = {key: val for key, val in self.model_dump().items() if key != "role_ids"}
        return UserCreateWithAudit(**data)

    def get_role_ids(self) -> list[str]:
        if self.role_ids is None:
            return []
        return self.role_ids


class UserUpdate(SQLModel):
    username: str | None = None
    password: str | None = None

    def with_audit(self, updated_by: str) -> "UserUpdateWithAudit":
        return UserUpdateWithAudit(**self.model_dump(), updated_by=updated_by)


class UserUpdateWithAudit(UserUpdate):
    updated_by: str


class UserUpdateWithRoles(UserUpdate):
    role_ids: list[str] | None = None

    def with_audit(self, updated_by: str) -> "UserUpdateWithRolesAndAudit":
        return UserUpdateWithRolesAndAudit(**self.model_dump(), updated_by=updated_by)


class UserUpdateWithRolesAndAudit(UserUpdateWithRoles):
    updated_by: str

    def get_user_update_with_audit(self) -> UserUpdateWithAudit:
        data = {key: val for key, val in self.model_dump().items() if key != "role_ids"}
        return UserUpdateWithAudit(**data)

    def get_role_ids(self) -> list[str]:
        if self.role_ids is None:
            return []
        return self.role_ids


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
    username: str = Field(index=True, unique=True)
    password: str


class UserRole(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    user_id: str = Field(index=True)
    role_id: str = Field(index=True)
    created_at: datetime.datetime | None
    created_by: str | None
