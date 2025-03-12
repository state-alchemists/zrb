import datetime

import ulid
from my_app_name.schema.permission import Permission
from my_app_name.schema.role import Role
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    username: str
    active: bool


class UserCreate(UserBase):
    password: str

    def with_audit(self, created_by: str) -> "UserCreateWithAudit":
        return UserCreateWithAudit(**self.model_dump(), created_by=created_by)


class UserCreateWithAudit(UserCreate):
    created_by: str


class UserCreateWithRoles(UserCreate):
    role_names: list[str] | None = None

    def with_audit(self, created_by: str) -> "UserCreateWithRolesAndAudit":
        return UserCreateWithRolesAndAudit(**self.model_dump(), created_by=created_by)


class UserCreateWithRolesAndAudit(UserCreateWithRoles):
    created_by: str

    def get_user_create_with_audit(self) -> UserCreateWithAudit:
        data = {
            key: val for key, val in self.model_dump().items() if key != "role_names"
        }
        return UserCreateWithAudit(**data)

    def get_role_names(self) -> list[str]:
        if self.role_names is None:
            return []
        return self.role_names


class UserUpdate(SQLModel):
    username: str | None = None
    password: str | None = None
    active: bool | None = None

    def with_audit(self, updated_by: str) -> "UserUpdateWithAudit":
        return UserUpdateWithAudit(
            **self.model_dump(exclude_none=True), updated_by=updated_by
        )


class UserUpdateWithAudit(UserUpdate):
    updated_by: str


class UserUpdateWithRoles(UserUpdate):
    role_names: list[str] | None = None

    def with_audit(self, updated_by: str) -> "UserUpdateWithRolesAndAudit":
        return UserUpdateWithRolesAndAudit(
            **self.model_dump(exclude_none=True), updated_by=updated_by
        )


class UserUpdateWithRolesAndAudit(UserUpdateWithRoles):
    updated_by: str

    def get_user_update_with_audit(self) -> UserUpdateWithAudit:
        data = {
            key: val
            for key, val in self.model_dump(exclude_none=True).items()
            if key != "role_names"
        }
        return UserUpdateWithAudit(**data)

    def get_role_names(self) -> list[str]:
        if self.role_names is None:
            return []
        return self.role_names


class UserResponse(UserBase):
    id: str
    role_names: list[str]
    permission_names: list[str]


class AuthUserResponse(UserResponse):
    is_super_user: bool
    is_guest: bool

    def has_permission(self, permission_name: str):
        return self.is_super_user or permission_name in self.permission_names

    def has_role(self, role_name: str):
        return self.is_super_user or role_name in self.role_names


class MultipleUserResponse(BaseModel):
    data: list[UserResponse]
    count: int


class UserCredentials(SQLModel):
    username: str
    password: str


class UserTokenData(SQLModel):
    access_token: str
    refresh_token: str
    access_token_expired_at: datetime.datetime
    refresh_token_expired_at: datetime.datetime


class UserSessionResponse(SQLModel):
    id: str
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str
    access_token_expired_at: datetime.datetime
    refresh_token_expired_at: datetime.datetime


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime = Field(index=True)
    created_by: str = Field(index=True)
    updated_at: datetime.datetime | None = Field(index=True)
    updated_by: str | None = Field(index=True)
    username: str = Field(index=True, unique=True)
    password: str
    active: bool = Field(index=True)


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    user_id: str = Field(index=True)
    role_id: str = Field(index=True)
    created_at: datetime.datetime | None
    created_by: str | None


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    user_id: str = Field(index=True)
    access_token: str = Field(index=True)
    refresh_token: str = Field(index=True)
    access_token_expired_at: datetime.datetime = Field(index=True)
    refresh_token_expired_at: datetime.datetime = Field(index=True)
