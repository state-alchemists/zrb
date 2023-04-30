from core.model import RepoModel
from module.auth.schema.group import (
    Group, GroupData, GroupResult
)


class GroupModel(
    RepoModel[Group, GroupData, GroupResult]
):
    schema_result_cls = GroupResult
