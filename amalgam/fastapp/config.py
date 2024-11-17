import os

APP_MODE = os.getenv("FASTAPP_MODE", "monolith")
APP_MODULES = [
    module.strip()
    for module in os.getenv("FASTAPP_MODULES", "").split(",")
    if module.strip() != ""
]
APP_PORT = int(os.getenv("FASTAPP_PORT", "3000"))
APP_COMMUNICATION = os.getenv(
    "FASTAPP_COMMUNICATION", "direct" if APP_MODE == "monolith" else "api"
)
APP_REPOSITORY_TYPE = os.getenv("APP_REPOSITORY_TYPE", "db")

_DEFAULT_ASYNC_DB_URL = "sqlite+aiosqlite:///monolith.db"
_DEFAULT_SYNC_DB_URL = "sqlite:///monolith.db"
if APP_MODE != "monolith":
    _DEFAULT_ASYNC_DB_URL = "sqlite+aiosqlite:///microservices.db"
    _DEFAULT_SYNC_DB_URL = "sqlite:///microservices.db"
APP_DB_URL = os.getenv("APP_DB_URL", _DEFAULT_ASYNC_DB_URL)
APP_DB_MIGRATION_URL = os.getenv("APP_DB_MIGRATION_URL", _DEFAULT_SYNC_DB_URL)

_DEFAULT_MIGRATION_TABLE = "migration_table"
if APP_MODE != "monolith" and len(APP_MODULES) > 0:
    _DEFAULT_MIGRATION_TABLE = f"{APP_MODULES[0]}_{_DEFAULT_MIGRATION_TABLE}"
APP_DB_MIGRATION_TABLE = os.getenv("APP_DB_MIGRATION_TABLE", _DEFAULT_MIGRATION_TABLE)

APP_AUTH_BASE_URL = os.getenv("FASTAPP_AUTH_BASE_URL", "http://localhost:3001")
