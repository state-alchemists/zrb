from fastapp_template.common.app import app
from fastapp_template.module.auth import route as auth_route
from fastapp_template.module.gateway import route as gateway_route

assert app
assert gateway_route
assert auth_route
