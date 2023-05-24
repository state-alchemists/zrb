from component.log import logger
from component.db_connection import engine
from module.log.entity.activity.repo import (
    ActivityRepo, ActivityDBRepo
)

activity_repo: ActivityRepo = ActivityDBRepo(
    logger=logger, engine=engine
)
