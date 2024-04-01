from integration.messagebus import publisher
from module.auth.entity.permission.model import PermissionModel
from module.auth.integration.repo.permission_repo import permission_repo

permission_model: PermissionModel = PermissionModel(permission_repo, publisher)
