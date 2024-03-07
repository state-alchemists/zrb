import logging
from abc import ABC, abstractmethod
from typing import Any, List, Mapping

from component.repo import DBEntityMixin, DBRepo, Repo
from module.auth.component import PasswordHasher
from module.auth.entity.group.repo import DBEntityGroup
from module.auth.entity.permission.repo import DBEntityPermission
from module.auth.entity.table import user_group, user_permission
from module.auth.integration import Base
from module.auth.schema.user import User, UserData, UserLogin
from sqlalchemy import Column, String, or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, relationship


class DBEntityUser(Base, DBEntityMixin):
    class Config:
        from_attributes = True

    __tablename__ = "users"
    username = Column(String)
    phone = Column(String)
    email = Column(String)
    description = Column(String)
    hashed_password = Column(String)
    permissions = relationship("DBEntityPermission", secondary=user_permission)
    groups = relationship("DBEntityGroup", secondary=user_group)


class UserRepo(Repo[User, UserData], ABC):
    @abstractmethod
    async def get_by_user_login(self, user_login: UserLogin) -> User:
        pass


class UserDBRepo(DBRepo[User, UserData], UserRepo):
    schema_cls = User
    db_entity_cls = DBEntityUser

    def __init__(
        self, logger: logging.Logger, engine: Engine, password_hasher: PasswordHasher
    ):
        super().__init__(logger, engine)
        self.password_hasher = password_hasher

    async def get_by_user_login(self, user_login: UserLogin) -> User:
        db = self._get_db_session()
        db_users: List[DBEntityUser] = []
        try:
            search_filter = or_(
                DBEntityUser.username == user_login.identity,
                DBEntityUser.phone == user_login.identity,
                DBEntityUser.email == user_login.identity,
            )
            db_users = [
                db_user
                for db_user in self._get_by_criterion(db, search_filter)
                if self.password_hasher.check_password(
                    user_login.password, db_user.hashed_password
                )
            ]
            if len(db_users) == 0:
                raise ValueError("Not found: Cannot find any user")
            return self._db_entity_to_schema(db, db_users[0])
        finally:
            db.close()

    def _schema_data_to_db_entity_map(
        self, db: Session, user_data: UserData
    ) -> Mapping[str, Any]:
        db_entity_map = super()._schema_data_to_db_entity_map(db, user_data)
        # Transform permissions
        db_entity_map["permissions"] = (
            db.query(DBEntityPermission)
            .filter(DBEntityPermission.id.in_(user_data.permissions))
            .all()
        )
        # Transform groups
        db_entity_map["groups"] = (
            db.query(DBEntityGroup).filter(DBEntityGroup.id.in_(user_data.groups)).all()
        )
        # add hashed password if necessary
        if user_data.password != "":
            db_entity_map["hashed_password"] = self.password_hasher.hash_password(
                user_data.password
            )  # noqa
        return db_entity_map
