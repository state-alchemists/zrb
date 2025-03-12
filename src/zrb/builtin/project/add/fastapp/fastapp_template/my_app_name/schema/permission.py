import datetime

import ulid
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class PermissionBase(SQLModel):
    name: str


class PermissionCreate(PermissionBase):
    description: str

    def with_audit(self, created_by: str) -> "PermissionCreateWithAudit":
        return PermissionCreateWithAudit(**self.model_dump(), created_by=created_by)


class PermissionCreateWithAudit(PermissionCreate):
    created_by: str


class PermissionUpdate(SQLModel):
    name: str | None = None
    description: str | None = None

    def with_audit(self, updated_by: str) -> "PermissionUpdateWithAudit":
        return PermissionUpdateWithAudit(
            **self.model_dump(exclude_none=True), updated_by=updated_by
        )


class PermissionUpdateWithAudit(PermissionUpdate):
    updated_by: str


class PermissionResponse(PermissionBase):
    id: str
    description: str


class MultiplePermissionResponse(BaseModel):
    data: list[PermissionResponse]
    count: int


class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime | None = Field(index=True)
    created_by: str | None = Field(index=True)
    updated_at: datetime.datetime | None = Field(index=True)
    updated_by: str | None = Field(index=True)
    name: str = Field(index=True, unique=True)
    description: str
