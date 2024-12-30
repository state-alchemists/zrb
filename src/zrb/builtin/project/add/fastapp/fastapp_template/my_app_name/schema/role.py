import datetime

import ulid
from my_app_name.schema.permission import Permission
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class RoleBase(SQLModel):
    name: str


class RoleCreate(RoleBase):
    description: str


class RoleCreateWithAudit(RoleCreate):
    created_by: str


class RoleUpdate(SQLModel):
    name: str | None = None
    description: str | None = None


class RoleUpdateWithAudit(RoleUpdate):
    updated_by: str


class RoleResponse(RoleBase):
    id: str
    permissions: list[Permission]


class MultipleRoleResponse(BaseModel):
    data: list[RoleResponse]
    count: int


class Role(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime | None = Field(index=True)
    created_by: str | None = Field(index=True)
    updated_at: datetime.datetime | None = Field(index=True)
    updated_by: str | None = Field(index=True)
    name: str = Field(index=True)
    description: str


class RolePermission(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    role_id: str = Field(index=True)
    permission_id: str = Field(index=True)
    created_at: datetime.datetime | None
    created_by: str | None
