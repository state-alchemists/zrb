from config import (
    APP_AUTH_ADMIN_EMAIL,
    APP_AUTH_ADMIN_PASSWORD,
    APP_AUTH_ADMIN_PHONE,
    APP_AUTH_ADMIN_USER_ID,
    APP_AUTH_ADMIN_USERNAME,
    APP_AUTH_GUEST_EMAIL,
    APP_AUTH_GUEST_PHONE,
    APP_AUTH_GUEST_USER_ID,
    APP_AUTH_GUEST_USERNAME,
)
from module.auth.schema.user import User

admin_user_password = APP_AUTH_ADMIN_PASSWORD

admin_user = User(
    id=APP_AUTH_ADMIN_USER_ID,
    username=APP_AUTH_ADMIN_USERNAME,
    email=APP_AUTH_ADMIN_EMAIL,
    phone=APP_AUTH_ADMIN_PHONE,
    groups=[],
    permissions=[],
    description="System administrator",
)

guest_user = User(
    id=APP_AUTH_GUEST_USER_ID,
    username=APP_AUTH_GUEST_USERNAME,
    email=APP_AUTH_GUEST_EMAIL,
    phone=APP_AUTH_GUEST_PHONE,
    groups=[],
    permissions=[],
    description="Visitor",
)
