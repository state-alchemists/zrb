from module.auth.component.repo.permission_repo import permission_repo
from module.auth.entity.permission.model import (
    PermissionModel, PermissionRepoModel
)

permission_model: PermissionModel = PermissionRepoModel(permission_repo)
