import os

APP_PATH = os.path.dirname(__file__)

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
APP_DB_URL = os.getenv(
    "APP_DB_URL",
    (
        f"sqlite:///{APP_PATH}/monolith.db"
        if APP_MODE == "monolith" or len(APP_MODULES) == 0
        else f"sqlite:///{APP_PATH}/{APP_MODULES[0]}_microservices.db"
    ),
)
APP_AUTH_SUPER_USER = os.getenv("FASTAPP_AUTH_SUPER_USER", "admin")
APP_AUTH_SUPER_USER_PASSWORD = os.getenv(
    "FASTAPP_AUTH_SUPER_USER_PASSWORD", "rich-atom-9523"
)

APP_AUTH_BASE_URL = os.getenv("FASTAPP_AUTH_BASE_URL", "http://localhost:3001")
APP_ANU_BASE_URL = os.getenv("FASTAPP_ANU_BASE_URL", "http://localhost:3002")
