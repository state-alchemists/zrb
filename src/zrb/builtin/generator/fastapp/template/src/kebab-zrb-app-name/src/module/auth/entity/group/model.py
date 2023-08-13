from module.log.core.historical_repo_model import HistoricalRepoModel
from module.auth.schema.group import (
    Group, GroupData, GroupResult
)


class GroupModel(
    HistoricalRepoModel[Group, GroupData, GroupResult]
):
    schema_result_cls = GroupResult
    log_entity_name = 'group'
