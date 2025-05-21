from zrb.config import CFG
from zrb.runner.web_config.config import WebConfig

web_config = WebConfig(
    port=CFG.WEB_HTTP_PORT,
    secret_key=CFG.WEB_SECRET_KEY,
    access_token_expire_minutes=CFG.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    refresh_token_expire_minutes=CFG.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
    access_token_cookie_name=CFG.WEB_ACCESS_TOKEN_COOKIE_NAME,
    refresh_token_cookie_name=CFG.WEB_REFRESH_TOKEN_COOKIE_NAME,
    enable_auth=CFG.WEB_ENABLE_AUTH,
    super_admin_username=CFG.WEB_SUPER_ADMIN_USERNAME,
    super_admin_password=CFG.WEB_SUPER_ADMIN_PASSWORD,
    guest_username=CFG.WEB_GUEST_USERNAME,
)
