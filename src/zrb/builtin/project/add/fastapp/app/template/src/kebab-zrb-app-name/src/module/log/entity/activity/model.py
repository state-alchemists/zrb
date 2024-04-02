from component.model import RepoModel
from module.log.schema.activity import Activity, ActivityData, ActivityResult


class ActivityModel(RepoModel[Activity, ActivityData, ActivityResult]):
    schema_result_cls = ActivityResult
