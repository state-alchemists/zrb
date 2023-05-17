from typing import Callable
from starlette.requests import Request
from module.auth.schema.token import AccessTokenData

AccessTokenScheme = Callable[[Request], AccessTokenData]
