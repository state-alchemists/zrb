from typing import Any, Mapping
from abc import ABC
from sqlalchemy import Column, String
from sqlalchemy.orm import Session, relationship
from core.repo import Repo, DBEntityMixin, DBRepo
from module.auth.schema.user import User, UserData
from module.auth.component import Base
from module.auth.entity.table import user_group, user_permission
from module.auth.entity.permission.repo import DBEntityPermission
from module.auth.entity.group.repo import DBEntityGroup


class DBEntityUser(Base, DBEntityMixin):
    __tablename__ = "users"
    username = Column(String)
    phone = Column(String)
    email = Column(String)
    description = Column(String)
    hashed_password = Column(String)
    permissions = relationship(
        "DBEntityPermission",
        secondary=user_permission, back_populates="users"
    )
    groups = relationship(
        "DBEntityGroup",
        secondary=user_group, back_populates="users"
    )


class UserRepo(Repo[User, UserData], ABC):
    pass


class UserDBRepo(
    DBRepo[User, UserData], UserRepo
):
    schema_cls = User
    db_entity_cls = DBEntityUser

    def _schema_data_to_db_entity_map(
        self, db: Session, user_data: UserData
    ) -> Mapping[str, Any]:
        return {
            'username': user_data.username,
            'phone': user_data.phone,
            'email': user_data.email,
            'hashed_password': user_data.password,
            'description': user_data.description,
            'permissions': db.query(DBEntityPermission).filter(
                DBEntityPermission.id.in_(user_data.permissions)
            ).all(),
            'groups': db.query(DBEntityGroup).filter(
                DBEntityGroup.id.in_(user_data.groups)
            ).all(),
            'created_at': user_data.created_at,
            'created_by': user_data.created_by,
            'updated_at': user_data.updated_at,
            'updated_by': user_data.updated_by,
        }
