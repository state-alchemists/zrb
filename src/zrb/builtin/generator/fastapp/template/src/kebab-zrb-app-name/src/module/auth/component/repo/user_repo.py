from module.auth.component.password_hasher import password_hasher
from component.log import logger
from component.db_connection import engine
from module.auth.entity.user.repo import (
    UserRepo, UserDBRepo
)

user_repo: UserRepo = UserDBRepo(
    logger=logger, engine=engine, password_hasher=password_hasher
)
