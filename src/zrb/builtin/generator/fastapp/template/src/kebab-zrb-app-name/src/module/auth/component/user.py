from config import (
    app_auth_admin_email,
    app_auth_admin_password,
    app_auth_admin_phone,
    app_auth_admin_user_id,
    app_auth_admin_username,
    app_auth_guest_email,
    app_auth_guest_phone,
    app_auth_guest_user_id,
    app_auth_guest_username,
)
from module.auth.schema.user import User

admin_user_password = app_auth_admin_password

admin_user = User(
    id=app_auth_admin_user_id,
    username=app_auth_admin_username,
    email=app_auth_admin_email,
    phone=app_auth_admin_phone,
    groups=[],
    permissions=[],
    description="System administrator",
)

guest_user = User(
    id=app_auth_guest_user_id,
    username=app_auth_guest_username,
    email=app_auth_guest_email,
    phone=app_auth_guest_phone,
    groups=[],
    permissions=[],
    description="Visitor",
)
