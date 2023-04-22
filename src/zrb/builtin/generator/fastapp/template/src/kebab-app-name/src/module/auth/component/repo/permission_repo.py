from component.log import logger
from component.db_connection import engine
from module.auth.entity.permission.repo import (
    PermissionRepo, PermissionDBRepo
)

permission_repo: PermissionRepo = PermissionDBRepo(
    logger=logger, engine=engine
)
