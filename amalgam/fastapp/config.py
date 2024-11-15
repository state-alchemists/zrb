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
APP_REPOSITORY_DB_URL = os.getenv("APP_REPOSITORY_DB_URL", "sqlite+aiosqlite://")
APP_LIBRARY_BASE_URL = os.getenv("FASTAPP_LIBRARY_BASE_URL", "http://localhost:3001")
