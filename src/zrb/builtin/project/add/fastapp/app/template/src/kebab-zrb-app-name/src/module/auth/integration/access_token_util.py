from config import (
    APP_AUTH_ACCESS_TOKEN_TYPE,
    APP_AUTH_JWT_TOKEN_ALGORITHM,
    APP_AUTH_JWT_TOKEN_SECRET_KEY,
)
from module.auth.component import AccessTokenUtil, JWTAccessTokenUtil


def init_token_util() -> AccessTokenUtil:
    if APP_AUTH_ACCESS_TOKEN_TYPE.lower() == "jwt":
        return JWTAccessTokenUtil(
            secret_key=APP_AUTH_JWT_TOKEN_SECRET_KEY,
            algorithm=APP_AUTH_JWT_TOKEN_ALGORITHM,
        )
    raise ValueError(f"Invalid auth token type: {APP_AUTH_ACCESS_TOKEN_TYPE}")


access_token_util = init_token_util()
