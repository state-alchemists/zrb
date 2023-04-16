from abc import ABC
from sqlalchemy import Column, String
from core.repo import Repo, DBEntityMixin, DBRepo
from module.auth.schema.permission import Permission, PermissionData
from module.auth.component import Base


class DBEntityPermission(Base, DBEntityMixin):
    __tablename__ = "permissions"
    name = Column(String)
    description = Column(String)


class PermissionRepo(Repo[Permission, PermissionData], ABC):
    pass


class PermissionDBRepo(
    DBRepo[Permission, PermissionData], PermissionRepo
):
    schema_cls = Permission
    db_entity_cls = DBEntityPermission
