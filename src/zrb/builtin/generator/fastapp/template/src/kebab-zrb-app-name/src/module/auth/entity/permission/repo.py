from abc import ABC, abstractmethod
from sqlalchemy import Column, String
from core.repo import Repo, DBEntityMixin, DBRepo
from module.auth.schema.permission import Permission, PermissionData
from module.auth.component import Base


class DBEntityPermission(Base, DBEntityMixin):
    __tablename__ = "permissions"
    name = Column(String)
    description = Column(String)


class PermissionRepo(Repo[Permission, PermissionData], ABC):
    @abstractmethod
    async def get_by_name(self, name: str) -> Permission:
        pass


class PermissionDBRepo(
    DBRepo[Permission, PermissionData], PermissionRepo
):
    schema_cls = Permission
    db_entity_cls = DBEntityPermission

    async def get_by_name(self, name: str) -> Permission:
        '''
        Find permission by name.
        '''
        db = self._get_db_session()
        try:
            search_filter = DBEntityPermission.name == name
            db_permission = self._get_one_by_criterion(db, search_filter)
            return self._db_entity_to_schema(db, db_permission)
        finally:
            db.close()
