from datetime import datetime, timedelta, timezone

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_schema.token import Token
from zrb.runner.web_util.user import get_user_by_credentials


def generate_tokens_by_credentials(
    web_auth_config: WebAuthConfig, username: str, password: str
) -> Token | None:
    if not web_auth_config.enable_auth:
        user = web_auth_config.default_user
    else:
        user = get_user_by_credentials(web_auth_config, username, password)
    if user is None:
        return None
    access_token = _generate_access_token(web_auth_config, user.username)
    refresh_token = _generate_refresh_token(web_auth_config, user.username)
    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


def regenerate_tokens(web_auth_config: WebAuthConfig, refresh_token: str) -> Token:
    from fastapi import HTTPException
    from jose import jwt

    # Decode and validate token
    try:
        payload = jwt.decode(
            refresh_token,
            web_auth_config.secret_key,
            options={"require_exp": True, "require_sub": True},
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = web_auth_config.find_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    # Create new token
    new_access_token = _generate_access_token(web_auth_config, username)
    new_refresh_token = _generate_refresh_token(web_auth_config, username)
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


def _generate_access_token(web_auth_config: WebAuthConfig, username: str) -> str:
    from jose import jwt

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=web_auth_config.access_token_expire_minutes
    )
    to_encode = {"sub": username, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, web_auth_config.secret_key)


def _generate_refresh_token(web_auth_config: WebAuthConfig, username: str) -> str:
    from jose import jwt

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=web_auth_config.refresh_token_expire_minutes
    )
    to_encode = {"sub": username, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, web_auth_config.secret_key)
