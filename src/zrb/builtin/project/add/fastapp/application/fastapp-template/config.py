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
APP_REPOSITORY_DB_URL = os.getenv("APP_REPOSITORY_DB_URL", "sqlite+aiosqlite://")
APP_LIBRARY_BASE_URL = os.getenv("APP_NAME_LIBRARY_BASE_URL", "http://localhost:3001")
