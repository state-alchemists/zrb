from typing import TYPE_CHECKING

from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_schema.user import User

if TYPE_CHECKING:
    # Import Request only for type checking to reduce runtime dependencies
    from fastapi import Request


def get_user_by_credentials(
    web_config: WebConfig, username: str, password: str
) -> User | None:
    user = web_config.find_user_by_username(username)
    if user is None or not user.is_password_match(password):
        return None
    return user


async def get_user_from_request(
    web_config: WebConfig, request: "Request"
) -> User | None:
    from fastapi.security import OAuth2PasswordBearer

    if not web_config.enable_auth:
        return web_config.default_user
    # Normally we use "Depends"
    get_bearer_token = OAuth2PasswordBearer(tokenUrl="/api/v1/login", auto_error=False)
    bearer_token = await get_bearer_token(request)
    token_user = _get_user_from_token(web_config, bearer_token)
    if token_user is not None:
        return token_user
    cookie_user = _get_user_from_cookie(web_config, request)
    if cookie_user is not None:
        return cookie_user
    return web_config.default_user


def _get_user_from_cookie(web_config: WebConfig, request: "Request") -> User | None:
    token = request.cookies.get(web_config.access_token_cookie_name)
    if token:
        return _get_user_from_token(web_config, token)
    return None


def _get_user_from_token(web_config: WebConfig, token: str) -> User | None:
    try:
        from jose import jwt

        payload = jwt.decode(
            token,
            web_config.secret_key,
            options={"require_sub": True, "require_exp": True},
        )
        username: str = payload.get("sub")
        if username is None:
            return None
        user = web_config.find_user_by_username(username)
        if user is None:
            return None
        return user
    except Exception:
        return None
