import datetime

import ulid
from my_app_name.schema.permission import Permission
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class RoleBase(SQLModel):
    name: str


class RoleCreate(RoleBase):
    description: str

    def with_audit(self, created_by: str) -> "RoleCreateWithAudit":
        return RoleCreateWithAudit(**self.model_dump(), created_by=created_by)


class RoleCreateWithAudit(RoleCreate):
    created_by: str


class RoleCreateWithPermissions(RoleCreate):
    permissions: list[str] | None = None

    def with_audit(self, created_by: str) -> "RoleCreateWithPermissionsAndAudit":
        return RoleCreateWithPermissionsAndAudit(
            **self.model_dump(), created_by=created_by
        )


class RoleCreateWithPermissionsAndAudit(RoleCreateWithPermissions):
    created_by: str

    def get_role_create_with_audit(self) -> RoleCreateWithAudit:
        data = {
            key: val for key, val in self.model_dump().items() if key != "permissions"
        }
        return RoleCreateWithAudit(**data)

    def get_permission_names(self) -> list[str]:
        if self.permissions is None:
            return []
        return self.permissions


class RoleUpdate(SQLModel):
    name: str | None = None
    description: str | None = None

    def with_audit(self, updated_by: str) -> "RoleUpdateWithAudit":
        return RoleUpdateWithAudit(**self.model_dump(), updated_by=updated_by)


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
