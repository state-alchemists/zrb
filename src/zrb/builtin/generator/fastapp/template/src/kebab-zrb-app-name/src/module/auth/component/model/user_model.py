from config import (
    app_auth_admin_active, app_auth_access_token_expire_seconds,
    app_auth_refresh_token_expire_seconds
)
from component.messagebus import publisher
from module.auth.component.repo.user_repo import user_repo
from module.auth.entity.user.model import UserModel
from module.auth.component import access_token_util, refresh_token_util
from module.auth.component.user import (
    admin_user, admin_user_password, guest_user
)
from module.auth.component.model.permission_model import permission_model


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
    admin_user_password=admin_user_password
)
