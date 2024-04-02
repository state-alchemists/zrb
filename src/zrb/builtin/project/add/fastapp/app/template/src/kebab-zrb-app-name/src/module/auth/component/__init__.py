from module.auth.component.access_token.scheme import (
    AccessTokenScheme,
    create_oauth2_bearer_access_token_scheme,
)
from module.auth.component.access_token.util import AccessTokenUtil, JWTAccessTokenUtil
from module.auth.component.authorizer.authorizer import Authorizer
from module.auth.component.authorizer.rpc_authorizer import RPCAuthorizer
from module.auth.component.password_hasher.bcrypt_password_hasher import (
    BcryptPasswordHasher,
)
from module.auth.component.password_hasher.password_hasher import PasswordHasher
from module.auth.component.refresh_token.util import (
    JWTRefreshTokenUtil,
    RefreshTokenUtil,
)

assert Authorizer
assert RPCAuthorizer
assert PasswordHasher
assert BcryptPasswordHasher
assert AccessTokenScheme
assert create_oauth2_bearer_access_token_scheme
assert AccessTokenUtil
assert JWTAccessTokenUtil
assert RefreshTokenUtil
assert JWTRefreshTokenUtil
