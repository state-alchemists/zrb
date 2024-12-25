from zrb.config import (
    WEB_ACCESS_TOKEN_COOKIE_NAME,
    WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
    WEB_ENABLE_AUTH,
    WEB_GUEST_USERNAME,
    WEB_HTTP_PORT,
    WEB_REFRESH_TOKEN_COOKIE_NAME,
    WEB_SECRET_KEY,
    WEB_SUPER_ADMIN_PASSWORD,
    WEB_SUPER_ADMIN_USERNAME,
)
from zrb.runner.web_config.config import WebConfig

web_config = WebConfig(
    port=WEB_HTTP_PORT,
    secret_key=WEB_SECRET_KEY,
    access_token_expire_minutes=WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    refresh_token_expire_minutes=WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
    access_token_cookie_name=WEB_ACCESS_TOKEN_COOKIE_NAME,
    refresh_token_cookie_name=WEB_REFRESH_TOKEN_COOKIE_NAME,
    enable_auth=WEB_ENABLE_AUTH,
    super_admin_username=WEB_SUPER_ADMIN_USERNAME,
    super_admin_password=WEB_SUPER_ADMIN_PASSWORD,
    guest_username=WEB_GUEST_USERNAME,
)
