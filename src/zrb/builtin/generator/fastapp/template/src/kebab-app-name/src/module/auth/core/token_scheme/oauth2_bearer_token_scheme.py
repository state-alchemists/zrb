from typing import Optional
from starlette.requests import Request
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from module.auth.core.token_util.token_util import TokenUtil
from module.auth.core.token_scheme.token_sheme import TokenScheme
from module.auth.schema.token import TokenData
from module.auth.schema.user import User


def create_oauth2_bearer_token_scheme(
    guest_user: User,
    token_util: TokenUtil,
    token_url: str,
    token_cookie_key: str = 'auth_token'
) -> TokenScheme:

    oauth2_scheme = OAuth2PasswordBearer(
        tokenUrl=token_url, auto_error=False
    )

    async def oauth2_bearer_token_scheme(
        request: Request,
        token: Optional[str] = Depends(oauth2_scheme)
    ) -> TokenData:
        token: Optional[str] = await oauth2_scheme(request)
        if token is None:
            request.cookies.get(token_cookie_key, None)
        if token is None:
            return TokenData(
                user_id=guest_user.id,
                username=guest_user.username,
                permission_names=[],
                expire_seconds=300
            )
        return token_util.decode(token)

    return oauth2_bearer_token_scheme
