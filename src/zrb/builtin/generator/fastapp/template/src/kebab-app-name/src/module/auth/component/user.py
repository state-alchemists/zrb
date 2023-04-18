from module.auth.schema.user import User
from config import (
    app_auth_admin_user_id, app_auth_admin_username, app_auth_admin_password,
    app_auth_admin_email, app_auth_admin_phone
)

admin = User(
    id=app_auth_admin_user_id,
    username=app_auth_admin_username,
    password=app_auth_admin_password,
    email=app_auth_admin_email,
    phone=app_auth_admin_phone
)
