from component.messagebus import publisher
from module.auth.component.repo.permission_repo import permission_repo
from module.auth.entity.permission.model import PermissionModel

permission_model: PermissionModel = PermissionModel(permission_repo, publisher)
