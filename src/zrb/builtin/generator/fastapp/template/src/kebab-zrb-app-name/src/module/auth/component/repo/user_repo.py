from component.db_connection import engine
from component.log import logger
from module.auth.component.password_hasher import password_hasher
from module.auth.entity.user.repo import UserDBRepo, UserRepo

user_repo: UserRepo = UserDBRepo(
    logger=logger, engine=engine, password_hasher=password_hasher
)
