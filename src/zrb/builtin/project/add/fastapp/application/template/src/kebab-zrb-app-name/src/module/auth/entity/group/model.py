from module.auth.schema.group import Group, GroupData, GroupResult
from module.log.component.historical_repo_model import HistoricalRepoModel


class GroupModel(HistoricalRepoModel[Group, GroupData, GroupResult]):
    schema_result_cls = GroupResult
    log_entity_name = "group"
