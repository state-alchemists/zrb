from module.auth.core import TokenScheme, create_oauth2_bearer_token_scheme
from module.auth.component.token_util import token_util
from module.auth.component.user import guest_user


token_scheme: TokenScheme = create_oauth2_bearer_token_scheme(
    guest_user=guest_user,
    token_util=token_util,
    token_url='/api/v1/login-oauth',
    token_cookie_key='auth_token'
)
