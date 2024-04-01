from config import (
    app_auth_jwt_token_algorithm,
    app_auth_jwt_token_secret_key,
    app_auth_refresh_token_type,
)
from module.auth.component import JWTRefreshTokenUtil, RefreshTokenUtil


def init_token_util() -> RefreshTokenUtil:
    if app_auth_refresh_token_type.lower() == "jwt":
        return JWTRefreshTokenUtil(
            secret_key=app_auth_jwt_token_secret_key,
            algorithm=app_auth_jwt_token_algorithm,
        )
    raise ValueError(f"Invalid auth token type: {app_auth_refresh_token_type}")


refresh_token_util = init_token_util()
