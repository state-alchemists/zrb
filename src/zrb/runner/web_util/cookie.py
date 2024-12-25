from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_schema.token import Token

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import Response


def set_auth_cookie(web_config: WebConfig, response: "Response", token: Token):
    access_token_max_age = web_config.access_token_expire_minutes * 60
    refresh_token_max_age = web_config.refresh_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    response.set_cookie(
        key=web_config.access_token_cookie_name,
        value=token.access_token,
        httponly=True,
        max_age=access_token_max_age,
        expires=now + timedelta(seconds=access_token_max_age),
    )
    response.set_cookie(
        key=web_config.refresh_token_cookie_name,
        value=token.refresh_token,
        httponly=True,
        max_age=refresh_token_max_age,
        expires=now + timedelta(seconds=refresh_token_max_age),
    )
