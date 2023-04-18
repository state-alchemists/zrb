from module.auth.component.repo import permission_repo
from module.auth.entity.permission.model import (
    PermissionModel, PermissionRepoModel
)
from module.auth.component.repo import group_repo
from module.auth.entity.group.model import (
    GroupModel, GroupRepoModel
)
from module.auth.component.repo import user_repo
from module.auth.entity.user.model import (
    UserModel, UserRepoModel
)


permission_model: PermissionModel = PermissionRepoModel(permission_repo)
group_model: GroupModel = GroupRepoModel(group_repo)
user_model: UserModel = UserRepoModel(user_repo)
