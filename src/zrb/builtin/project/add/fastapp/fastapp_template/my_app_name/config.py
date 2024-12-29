import os

APP_PATH = os.path.dirname(__file__)
APP_VERSION = "0.1.0"

APP_GATEWAY_VIEW_PATH = os.path.join(APP_PATH, "module", "gateway", "view")
APP_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH = os.getenv(
    "MY_APP_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH",
    os.path.join("template", "default.html"),
)
_DEFAULT_CSS_PATH = "/static/pico-css/pico.min.css"
APP_GATEWAY_CSS_PATH_LIST = [
    path
    for path in os.getenv("MY_APP_GATEWAY_CSS_PATH", _DEFAULT_CSS_PATH).split(":")
    if path != ""
]
APP_GATEWAY_JS_PATH_LIST = [
    path for path in os.getenv("MY_APP_GATEWAY_JS_PATH", "").split(":") if path != ""
]
APP_GATEWAY_TITLE = os.getenv("MY_APP_GATEWAY_TITLE", "My App Name")
APP_GATEWAY_SUBTITLE = os.getenv("MY_APP_GATEWAY_SUBTITLE", "Just Another App")
APP_GATEWAY_LOGO_PATH = os.getenv(
    "MY_APP_GATEWAY_LOGO", "/static/images/android-chrome-192x192.png"
)
APP_GATEWAY_FAVICON_PATH = os.getenv(
    "MY_APP_GATEWAY_FAVICON", "/static/images/favicon-32x32.png"
)

APP_MODE = os.getenv("MY_APP_NAME_MODE", "monolith")
APP_MODULES = [
    module.strip()
    for module in os.getenv("MY_APP_NAME_MODULES", "").split(",")
    if module.strip() != ""
]
APP_MAIN_MODULE = APP_MODULES[0] if len(APP_MODULES) > 0 else None
APP_PORT = int(os.getenv("MY_APP_NAME_PORT", "3000"))
APP_COMMUNICATION = os.getenv(
    "MY_APP_NAME_COMMUNICATION", "direct" if APP_MODE == "monolith" else "api"
)
APP_REPOSITORY_TYPE = os.getenv("APP_REPOSITORY_TYPE", "db")
APP_DB_URL = os.getenv(
    "MY_APP_NAME_DB_URL",
    (
        f"sqlite:///{APP_PATH}/monolith.db"
        if APP_MODE == "monolith" or len(APP_MODULES) == 0
        else f"sqlite:///{APP_PATH}/{APP_MODULES[0]}_microservices.db"
    ),
)
APP_AUTH_SUPER_USER = os.getenv("MY_APP_NAME_AUTH_SUPER_USER", "admin")
APP_AUTH_SUPER_USER_PASSWORD = os.getenv(
    "MY_APP_NAME_AUTH_SUPER_USER_PASSWORD", "my-secure-password"
)

APP_AUTH_BASE_URL = os.getenv("MY_APP_NAME_AUTH_BASE_URL", "http://localhost:3001")
