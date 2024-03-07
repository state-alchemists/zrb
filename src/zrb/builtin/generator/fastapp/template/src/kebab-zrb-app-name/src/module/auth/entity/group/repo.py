from abc import ABC
from typing import Any, Mapping

from component.repo import DBEntityMixin, DBRepo, Repo
from module.auth.entity.permission.repo import DBEntityPermission
from module.auth.entity.table import group_permission
from module.auth.integration import Base
from module.auth.schema.group import Group, GroupData
from sqlalchemy import Column, String
from sqlalchemy.orm import Session, relationship


class DBEntityGroup(Base, DBEntityMixin):
    class Config:
        from_attributes = True

    __tablename__ = "groups"
    name = Column(String)
    description = Column(String)
    permissions = relationship("DBEntityPermission", secondary=group_permission)


class GroupRepo(Repo[Group, GroupData], ABC):
    pass


class GroupDBRepo(DBRepo[Group, GroupData], GroupRepo):
    schema_cls = Group
    db_entity_cls = DBEntityGroup

    def _schema_data_to_db_entity_map(
        self, db: Session, group_data: GroupData
    ) -> Mapping[str, Any]:
        db_entity_map = super()._schema_data_to_db_entity_map(db, group_data)
        # Transform permissions
        db_entity_map["permissions"] = (
            db.query(DBEntityPermission)
            .filter(DBEntityPermission.id.in_(group_data.permissions))
            .all()
        )
        return db_entity_map
