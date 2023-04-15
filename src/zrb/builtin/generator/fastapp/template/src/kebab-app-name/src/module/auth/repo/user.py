from sqlalchemy import Column, String
from core.repo import DBEntityMixin, DBRepo
from schema import User, UserData
from module.auth.repo._base import Base


class DBEntityUser(Base, DBEntityMixin):
    __tablename__ = "users"
    name = Column(String)
    email = Column(String)


class UserRepo(DBRepo[DBEntityUser, User, UserData]):
    schema_class = User
    db_entity_class = DBEntityUser
