from module.log.component.repo.activity_repo import (
    activity_repo
)
from module.log.entity.activity.model import (
    ActivityModel
)

activity_model: ActivityModel = ActivityModel(
    activity_repo
)
