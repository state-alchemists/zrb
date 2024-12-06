import datetime

import ulid
from sqlmodel import Field, SQLModel


class PermissionBase(SQLModel):
    name: str


class PermissionCreate(PermissionBase):
    description: str


class PermissionUpdate(SQLModel):
    name: str | None = None
    description: str | None = None


class PermissionResponse(PermissionBase):
    id: str


class Permission(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime | None
    created_by: str | None
    updated_at: datetime.datetime | None
    updated_by: str | None
    name: str
    description: str
