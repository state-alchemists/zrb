from module.auth.component.repo import permission_repo
from module.auth.entity.permission.model import (
    PermissionModel, PermissionRepoModel
)

permission_model: PermissionModel = PermissionRepoModel(permission_repo)