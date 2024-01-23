from component.db_connection import engine
from component.log import logger
from module.log.entity.activity.repo import ActivityDBRepo, ActivityRepo

activity_repo: ActivityRepo = ActivityDBRepo(logger=logger, engine=engine)
