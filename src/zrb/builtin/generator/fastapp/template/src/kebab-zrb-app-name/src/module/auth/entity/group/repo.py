from typing import Any, Mapping
from abc import ABC
from sqlalchemy import Column, String
from sqlalchemy.orm import Session, relationship
from core.repo import Repo, DBEntityMixin, DBRepo
from module.auth.schema.group import Group, GroupData
from module.auth.component import Base
from module.auth.entity.table import group_permission
from module.auth.entity.permission.repo import DBEntityPermission


class DBEntityGroup(Base, DBEntityMixin):
    __tablename__ = "groups"
    name = Column(String)
    description = Column(String)
    permissions = relationship(
        "DBEntityPermission",
        secondary=group_permission
    )


class GroupRepo(Repo[Group, GroupData], ABC):
    pass


class GroupDBRepo(
    DBRepo[Group, GroupData], GroupRepo
):
    schema_cls = Group
    db_entity_cls = DBEntityGroup

    def _schema_data_to_db_entity_map(
        self, db: Session, group_data: GroupData
    ) -> Mapping[str, Any]:
        db_entity_map = super()._schema_data_to_db_entity_map(db, group_data)
        # Transform permissions
        db_entity_map['permissions'] = db.query(DBEntityPermission).filter(
            DBEntityPermission.id.in_(group_data.permissions)
        ).all()
        return db_entity_map
