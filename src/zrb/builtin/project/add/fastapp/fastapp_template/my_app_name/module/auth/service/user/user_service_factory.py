from my_app_name.common.logger_factory import logger
from my_app_name.config import (
    APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    APP_AUTH_GUEST_USER,
    APP_AUTH_GUEST_USER_PERMISSIONS,
    APP_AUTH_MAX_PARALLEL_SESSION,
    APP_AUTH_PRIORITIZE_NEW_SESSION,
    APP_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
    APP_AUTH_SECRET_KEY,
    APP_AUTH_SUPER_USER,
    APP_AUTH_SUPER_USER_PASSWORD,
)
from my_app_name.module.auth.service.user.repository.user_repository_factory import (
    user_repository,
)
from my_app_name.module.auth.service.user.user_service import (
    UserService,
    UserServiceConfig,
)

user_service = UserService(
    logger,
    user_repository=user_repository,
    config=UserServiceConfig(
        super_user=APP_AUTH_SUPER_USER,
        super_user_password=APP_AUTH_SUPER_USER_PASSWORD,
        guest_user=APP_AUTH_GUEST_USER,
        guest_user_permissions=APP_AUTH_GUEST_USER_PERMISSIONS,
        max_parallel_session=APP_AUTH_MAX_PARALLEL_SESSION,
        access_token_expire_minutes=APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_minutes=APP_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
        secret_key=APP_AUTH_SECRET_KEY,
        prioritize_new_session=APP_AUTH_PRIORITIZE_NEW_SESSION,
    ),
)
