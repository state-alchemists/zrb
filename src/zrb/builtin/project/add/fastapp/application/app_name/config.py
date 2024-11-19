import os

APP_MODE = os.getenv("APP_NAME_MODE", "monolith")
APP_MODULES = [
    module.strip()
    for module in os.getenv("APP_NAME_MODULES", "").split(",")
    if module.strip() != ""
]
APP_PORT = int(os.getenv("APP_NAME_PORT", "3000"))
APP_COMMUNICATION = os.getenv(
    "APP_NAME_COMMUNICATION", "direct" if APP_MODE == "monolith" else "api"
)
APP_REPOSITORY_TYPE = os.getenv("APP_REPOSITORY_TYPE", "db")

_DEFAULT_DB_URL = "sqlite:///monolith.db"
if APP_MODE != "monolith":
    _DEFAULT_DB_URL = "sqlite:///microservices.db"
APP_DB_URL = os.getenv("APP_DB_URL", _DEFAULT_DB_URL)

_DEFAULT_MIGRATION_TABLE = "migration_table"
if APP_MODE != "monolith" and len(APP_MODULES) > 0:
    _DEFAULT_MIGRATION_TABLE = f"{APP_MODULES[0]}_{_DEFAULT_MIGRATION_TABLE}"
APP_DB_MIGRATION_TABLE = os.getenv("APP_DB_MIGRATION_TABLE", _DEFAULT_MIGRATION_TABLE)

APP_AUTH_BASE_URL = os.getenv("APP_NAME_AUTH_BASE_URL", "http://localhost:3001")
