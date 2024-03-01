from integration.app import app
from module.auth.register_module import register_auth
from module.log.register_module import register_log

# Make sure app is loaded.
# Uvicorn or adny ASGII server you use will pick it up and run the app.
assert app
register_auth()
register_log()
