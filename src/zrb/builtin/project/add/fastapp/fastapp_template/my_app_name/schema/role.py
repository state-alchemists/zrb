import datetime

import ulid
from my_app_name.schema.permission import Permission
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


class Role(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime | None
    created_by: str | None
    updated_at: datetime.datetime | None
    updated_by: str | None
    name: str
    description: str


class RolePermission(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    role_id: str
    permission_id: str
    created_at: datetime.datetime | None
    created_by: str | None
