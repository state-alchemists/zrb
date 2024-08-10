from config import (
    APP_AUTH_JWT_TOKEN_ALGORITHM,
    APP_AUTH_JWT_TOKEN_SECRET_KEY,
    APP_AUTH_REFRESH_TOKEN_TYPE,
)
from module.auth.component import JWTRefreshTokenUtil, RefreshTokenUtil


def init_token_util() -> RefreshTokenUtil:
    if APP_AUTH_REFRESH_TOKEN_TYPE.lower() == "jwt":
        return JWTRefreshTokenUtil(
            secret_key=APP_AUTH_JWT_TOKEN_SECRET_KEY,
            algorithm=APP_AUTH_JWT_TOKEN_ALGORITHM,
        )
    raise ValueError(f"Invalid auth token type: {APP_AUTH_REFRESH_TOKEN_TYPE}")


refresh_token_util = init_token_util()
