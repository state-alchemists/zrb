from integration.messagebus import publisher
from module.auth.entity.group.model import GroupModel
from module.auth.integration.repo.group_repo import group_repo

group_model: GroupModel = GroupModel(group_repo, publisher)
