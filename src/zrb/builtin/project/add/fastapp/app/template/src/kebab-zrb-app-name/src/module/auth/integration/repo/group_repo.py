from integration.db_connection import engine
from integration.log import logger
from module.auth.entity.group.repo import GroupDBRepo, GroupRepo

group_repo: GroupRepo = GroupDBRepo(logger=logger, engine=engine)
