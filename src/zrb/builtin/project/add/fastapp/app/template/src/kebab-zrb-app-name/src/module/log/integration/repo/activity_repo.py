from integration.db_connection import engine
from integration.log import logger
from module.log.entity.activity.repo import ActivityDBRepo, ActivityRepo

activity_repo: ActivityRepo = ActivityDBRepo(logger=logger, engine=engine)
