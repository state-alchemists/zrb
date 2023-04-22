from typing import Callable
from starlette.requests import Request
from module.auth.schema.token import TokenData

TokenScheme = Callable[[Request], TokenData]
