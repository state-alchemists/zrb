from component.app import app
from config import app_db_auto_migrate
from migrate import migrate
from module.auth import register_auth

if app_db_auto_migrate:
    # perform DB migration
    migrate()

# Make sure app is loaded.
# Uvicorn or adny ASGII server you use will pick it up and run the app.
assert app
register_auth()
