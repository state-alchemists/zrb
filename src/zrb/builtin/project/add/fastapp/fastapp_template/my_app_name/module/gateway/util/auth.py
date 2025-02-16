import datetime

from fastapi import Depends, Request, Response
from fastapi.security import OAuth2PasswordBearer
from my_app_name.config import (
    APP_AUTH_ACCESS_TOKEN_COOKIE_NAME,
    APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    APP_AUTH_REFRESH_TOKEN_COOKIE_NAME,
    APP_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
)
from my_app_name.module.auth.client.auth_client_factory import auth_client
from my_app_name.schema.user import AuthUserResponse, UserSessionResponse
from typing_extensions import Annotated

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/user-sessions", auto_error=False)


def get_refresh_token(request: Request, refresh_token: str | None) -> str | None:
    if refresh_token is not None and refresh_token != "":
        return refresh_token
    cookie_refresh_token = request.cookies.get(APP_AUTH_REFRESH_TOKEN_COOKIE_NAME)
    if cookie_refresh_token is not None and cookie_refresh_token != "":
        return cookie_refresh_token
    return None


async def get_current_user(
    request: Request,
    response: Response,
    bearer_access_token: Annotated[str, Depends(oauth2_scheme)],
) -> AuthUserResponse:
    # Bearer token exists
    if bearer_access_token is not None and bearer_access_token != "":
        return await auth_client.get_current_user(bearer_access_token)
    cookie_access_token = request.cookies.get(APP_AUTH_ACCESS_TOKEN_COOKIE_NAME)
    # Cookie exists
    if cookie_access_token is not None and cookie_access_token != "":
        cookie_user = await auth_client.get_current_user(cookie_access_token)
        if cookie_user.is_guest:
            # If user is guest, the cookie is not needed
            unset_user_session_cookie(response)
        return cookie_user
    # No bearer token or cookie
    return await auth_client.get_current_user("")


def set_user_session_cookie(response: Response, user_session: UserSessionResponse):
    response.set_cookie(
        key=APP_AUTH_ACCESS_TOKEN_COOKIE_NAME,
        value=user_session.access_token,
        httponly=True,
        max_age=60 * APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
        expires=user_session.access_token_expired_at.astimezone(datetime.timezone.utc),
    )
    response.set_cookie(
        key=APP_AUTH_REFRESH_TOKEN_COOKIE_NAME,
        value=user_session.refresh_token,
        httponly=True,
        max_age=60 * APP_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
        expires=user_session.refresh_token_expired_at.astimezone(datetime.timezone.utc),
    )


def unset_user_session_cookie(response: Response):
    response.delete_cookie(APP_AUTH_ACCESS_TOKEN_COOKIE_NAME)
    response.delete_cookie(APP_AUTH_REFRESH_TOKEN_COOKIE_NAME)
