from config import (
    app_auth_access_token_expire_seconds,
    app_auth_admin_active,
    app_auth_refresh_token_expire_seconds,
)
from integration.messagebus import publisher
from module.auth.entity.user.model import UserModel
from module.auth.integration import access_token_util, refresh_token_util
from module.auth.integration.model.permission_model import permission_model
from module.auth.integration.repo.user_repo import user_repo
from module.auth.integration.user import admin_user, admin_user_password, guest_user

user_model: UserModel = UserModel(
    repo=user_repo,
    publisher=publisher,
    permission_model=permission_model,
    access_token_util=access_token_util,
    access_token_expire_seconds=app_auth_access_token_expire_seconds,
    refresh_token_util=refresh_token_util,
    refresh_token_expire_seconds=app_auth_refresh_token_expire_seconds,
    guest_user=guest_user,
    admin_user=admin_user if app_auth_admin_active else None,
    admin_user_password=admin_user_password,
)
