from module.auth.component.repo.group_repo import group_repo
from module.auth.entity.group.model import (
    GroupModel, GroupRepoModel
)


group_model: GroupModel = GroupRepoModel(group_repo)