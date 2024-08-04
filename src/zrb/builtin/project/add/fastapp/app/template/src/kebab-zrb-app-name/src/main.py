from integration.app.app import app
from module.auth.register_module import register_auth
from module.log.register_module import register_log

assert app
register_auth()
register_log()
