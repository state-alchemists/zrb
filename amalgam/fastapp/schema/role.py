import datetime

import ulid
from sqlmodel import Field, SQLModel


class RoleBase(SQLModel):
    name: str


class RoleCreate(RoleBase):
    description: str


class RoleUpdate(SQLModel):
    name: str | None = None
    description: str | None = None


class RoleResponse(RoleBase):
    id: str


class Role(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime | None
    created_by: str | None
    updated_at: datetime.datetime | None
    updated_by: str | None
    name: str
    description: str
