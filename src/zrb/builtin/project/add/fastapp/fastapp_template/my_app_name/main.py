from my_app_name.common.app_factory import app
from my_app_name.module.auth import route as auth_route
from my_app_name.module.gateway import route as gateway_route

assert app
assert gateway_route
assert auth_route
