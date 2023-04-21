from config import app_auth_token_expire_seconds, app_auth_admin_active
from module.auth.component.repo import user_repo
from module.auth.entity.user.model import (
    UserModel, UserRepoModel
)
from module.auth.component.token_util import token_util
from module.auth.component.user import admin_user, admin_user_password
from module.auth.component.model.permission_model import permission_model


user_model: UserModel = UserRepoModel(
    repo=user_repo,
    permission_model=permission_model,
    token_util=token_util,
    expire_seconds=app_auth_token_expire_seconds,
    admin_user=admin_user if app_auth_admin_active else None,
    admin_user_password=admin_user_password
)
