from .common.app_factory import app
from .module.auth import route as auth_route
from .module.gateway import route as gateway_route

assert app
assert gateway_route
assert auth_route
