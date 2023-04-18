from component.log import logger
from component.db_connection import engine
from module.auth.entity.permission.repo import (
    PermissionRepo, PermissionDBRepo
)
from module.auth.entity.group.repo import (
    GroupRepo, GroupDBRepo
)
from module.auth.entity.user.repo import (
    UserRepo, UserDBRepo
)


permission_repo: PermissionRepo = PermissionDBRepo(
    logger=logger, engine=engine
)
group_repo: GroupRepo = GroupDBRepo(
    logger=logger, engine=engine
)
user_repo: UserRepo = UserDBRepo(
    logger=logger, engine=engine
)
