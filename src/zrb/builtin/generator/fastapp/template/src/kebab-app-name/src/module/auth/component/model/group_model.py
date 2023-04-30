from module.auth.component.repo.group_repo import group_repo
from module.auth.entity.group.model import GroupModel

group_model: GroupModel = GroupModel(group_repo)
