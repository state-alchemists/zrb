from module.log.entity.activity.model import ActivityModel
from module.log.integration.repo.activity_repo import activity_repo

activity_model: ActivityModel = ActivityModel(activity_repo)
