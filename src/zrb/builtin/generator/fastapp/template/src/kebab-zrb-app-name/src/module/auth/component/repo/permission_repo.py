from component.db_connection import engine
from component.log import logger
from module.auth.entity.permission.repo import PermissionDBRepo, PermissionRepo

permission_repo: PermissionRepo = PermissionDBRepo(logger=logger, engine=engine)
