import os

APP_MODE = os.getenv("FASTAPP_APP_MODE", "monolith")
APP_MODULES = [
    module.strip()
    for module in os.getenv("FASTAPP_APP_MODULES", "").split(",")
    if module.strip() != ""
]
APP_PORT = int(os.getenv("FASTAPP_APP_PORT", "3000"))

APP_COMMUNICATION = os.getenv(
    "FASTAPP_APP_COMMUNICATION",
    "direct" if APP_MODE == "monolith" else "api"
)
APP_LIBRARY_BASE_URL = os.getenv(
    "FASTAPP_APP_LIBRARY_BASE_URL", "http://localhost:3001"
)
