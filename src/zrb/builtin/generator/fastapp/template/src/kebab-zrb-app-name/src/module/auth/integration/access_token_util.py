from config import (
    app_auth_access_token_type,
    app_auth_jwt_token_algorithm,
    app_auth_jwt_token_secret_key,
)
from module.auth.component import AccessTokenUtil, JWTAccessTokenUtil


def init_token_util() -> AccessTokenUtil:
    if app_auth_access_token_type.lower() == "jwt":
        return JWTAccessTokenUtil(
            secret_key=app_auth_jwt_token_secret_key,
            algorithm=app_auth_jwt_token_algorithm,
        )
    raise ValueError(f"Invalid auth token type: {app_auth_access_token_type}")


access_token_util = init_token_util()
