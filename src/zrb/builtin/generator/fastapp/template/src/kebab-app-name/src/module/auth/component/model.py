from config import app_auth_token_expire_seconds
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
from module.auth.component.token_util import token_util


permission_model: PermissionModel = PermissionRepoModel(permission_repo)
group_model: GroupModel = GroupRepoModel(group_repo)
user_model: UserModel = UserRepoModel(
    user_repo, token_util, expire_seconds=app_auth_token_expire_seconds
)

