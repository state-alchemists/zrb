from config import (
    APP_AUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
    APP_AUTH_ADMIN_ACTIVE,
    APP_AUTH_REFRESH_TOKEN_EXPIRE_SECONDS,
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
    access_token_expire_seconds=APP_AUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
    refresh_token_util=refresh_token_util,
    refresh_token_expire_seconds=APP_AUTH_REFRESH_TOKEN_EXPIRE_SECONDS,
    guest_user=guest_user,
    admin_user=admin_user if APP_AUTH_ADMIN_ACTIVE else None,
    admin_user_password=admin_user_password,
)
