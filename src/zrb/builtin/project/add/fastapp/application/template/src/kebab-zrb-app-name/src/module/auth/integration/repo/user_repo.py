from integration.db_connection import engine
from integration.log import logger
from module.auth.entity.user.repo import UserDBRepo, UserRepo
from module.auth.integration.password_hasher import password_hasher

user_repo: UserRepo = UserDBRepo(
    logger=logger, engine=engine, password_hasher=password_hasher
)
