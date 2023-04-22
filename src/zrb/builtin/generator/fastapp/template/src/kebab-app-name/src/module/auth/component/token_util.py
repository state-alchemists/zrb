from config import (
    app_auth_token_type, app_auth_jwt_token_algorithm,
    app_auth_jwt_token_secret_key
)
from module.auth.core import TokenUtil, JWTTokenUtil


def init_token_util() -> TokenUtil:
    if app_auth_token_type.lower() == 'jwt':
        return JWTTokenUtil(
            secret_key=app_auth_jwt_token_secret_key,
            algorithm=app_auth_jwt_token_algorithm
        )
    raise ValueError(f'Invalid auth token type: {app_auth_token_type}')


token_util = init_token_util()
