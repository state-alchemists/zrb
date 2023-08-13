from component.log import logger
from component.db_connection import engine

from module.auth.entity.group.repo import (
    GroupRepo, GroupDBRepo
)

group_repo: GroupRepo = GroupDBRepo(
    logger=logger, engine=engine
)
