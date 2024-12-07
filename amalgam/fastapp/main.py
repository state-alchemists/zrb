from fastapp.common.app import app
from fastapp.module.auth import route as auth_route
from fastapp.module.gateway import route as gateway_route

assert app
assert gateway_route
assert auth_route
