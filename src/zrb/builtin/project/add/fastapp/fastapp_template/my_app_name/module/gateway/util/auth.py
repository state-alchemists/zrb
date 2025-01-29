from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from my_app_name.config import APP_AUTH_ACCESS_TOKEN_COOKIE_NAME
from my_app_name.module.auth.client.auth_client_factory import auth_client
from my_app_name.schema.user import AuthUserResponse
from typing_extensions import Annotated

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/user-sessions", auto_error=False)


async def get_current_user(
    request: Request, bearer_access_token: Annotated[str, Depends(oauth2_scheme)]
) -> AuthUserResponse:
    bearer_user = await auth_client.get_current_user(bearer_access_token)
    if bearer_user is None or bearer_user.is_guest:
        cookie_access_token = request.cookies.get(APP_AUTH_ACCESS_TOKEN_COOKIE_NAME)
        if cookie_access_token is not None and cookie_access_token != "":
            return await auth_client.get_current_user(cookie_access_token)
    return bearer_user
