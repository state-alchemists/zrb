from module.auth.core.password_hasher.password_hasher import PasswordHasher
from module.auth.core.password_hasher.bcrypt_password_hasher import (
    BcryptPasswordHasher
)

password_hasher: PasswordHasher = BcryptPasswordHasher()
