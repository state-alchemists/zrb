from module.auth.component.authorizer import authorizer
from module.auth.component.base import Base
from module.auth.component.password_hasher import password_hasher
from module.auth.component.token_scheme import access_token_scheme
from module.auth.component.token_util import access_token_util
from module.auth.component.user import (
    admin_user, admin_user_password, guest_user
)

assert authorizer
assert Base
assert password_hasher
assert access_token_scheme
assert access_token_util
assert admin_user
assert admin_user_password
assert guest_user
