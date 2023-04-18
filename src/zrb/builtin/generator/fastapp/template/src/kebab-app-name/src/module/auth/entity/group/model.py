from abc import ABC
from core.model import Model, RepoModel
from module.auth.schema.group import (
    Group, GroupData, GroupResult
)


class GroupModel(
    Model[Group, GroupData, GroupResult], ABC
):
    pass


class GroupRepoModel(
    RepoModel[Group, GroupData, GroupResult], GroupModel
):
    schema_result_cls = GroupResult
