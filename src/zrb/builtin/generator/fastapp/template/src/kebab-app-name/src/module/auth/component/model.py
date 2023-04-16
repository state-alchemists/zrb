from module.auth.entity.permission.model import (
    PermissionModel, PermissionRepoModel
)
from module.auth.component.repo import permission_repo

permission_model: PermissionModel = PermissionRepoModel(permission_repo)
