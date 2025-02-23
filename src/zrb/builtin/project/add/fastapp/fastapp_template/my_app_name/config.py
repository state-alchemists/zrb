import os

TRUE_STRS = ["true", "1", "yes", "y", "active", "on"]
FALSE_STRS = ["false", "0", "no", "n", "inactive", "off"]

APP_PATH = os.path.dirname(__file__)
APP_VERSION = "0.1.0"

APP_GATEWAY_VIEW_PATH = os.path.join(APP_PATH, "module", "gateway", "view")
APP_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH = os.getenv(
    "MY_APP_NAME_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH",
    os.path.join("template", "default.html"),
)
APP_GATEWAY_PICO_CSS_COLOR = os.getenv("MY_APP_NAME_GATEWAY_PICO_CSS_COLOR", "")
APP_GATEWAY_PICO_CSS_PATH = (
    "/static/pico-css/pico.min.css"
    if APP_GATEWAY_PICO_CSS_COLOR == ""
    else f"/static/pico-css/pico.{APP_GATEWAY_PICO_CSS_COLOR}.min.css"
)
APP_GATEWAY_CSS_PATH_LIST = [
    path
    for path in os.getenv("MY_APP_NAME_GATEWAY_CSS_PATH", "").split(":")
    if path != ""
]
APP_GATEWAY_JS_PATH_LIST = [
    path
    for path in os.getenv("MY_APP_NAME_GATEWAY_JS_PATH", "").split(":")
    if path != ""
]
APP_GATEWAY_TITLE = os.getenv("MY_APP_NAME_GATEWAY_TITLE", "My App Name")
APP_GATEWAY_SUBTITLE = os.getenv("MY_APP_NAME_GATEWAY_SUBTITLE", "Just Another App")
APP_GATEWAY_LOGO_PATH = os.getenv(
    "MY_APP_NAME_GATEWAY_LOGO", "/static/images/android-chrome-192x192.png"
)
APP_GATEWAY_FOOTER = os.getenv(
    "MY_APP_NAME_GATEWAY_FOOTER", f"{APP_GATEWAY_TITLE} &copy; 2025"
)
APP_GATEWAY_FAVICON_PATH = os.getenv(
    "MY_APP_NAME_GATEWAY_FAVICON", "/static/images/favicon-32x32.png"
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
APP_AUTH_GUEST_USER = os.getenv("MY_APP_NAME_AUTH_GUEST_USER", "user")
APP_AUTH_GUEST_USER_PERMISSIONS = [
    permission_name.strip()
    for permission_name in os.getenv(
        "MY_APP_NAME_AUTH_GUEST_USER_PERMISSIONS", ""
    ).split(",")
    if permission_name.strip() != ""
]
APP_AUTH_MAX_PARALLEL_SESSION = int(
    os.getenv("MY_APP_NAME_AUTH_MAX_PARALLEL_SESSION", "1")
)
APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("MY_APP_NAME_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
APP_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("MY_APP_NAME_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES", "1440")
)
APP_AUTH_ACCESS_TOKEN_COOKIE_NAME = os.getenv(
    "MY_APP_NAME_AUTH_ACCESS_TOKEN_COOKIE_NAME", "access_token"
)
APP_AUTH_REFRESH_TOKEN_COOKIE_NAME = os.getenv(
    "MY_APP_NAME_AUTH_REFRESH_TOKEN_COOKIE_NAME", "refresh_token"
)
APP_AUTH_SECRET_KEY = os.getenv("MY_APP_NAME_AUTH_SECRET_KEY", "my-secret-key")
APP_AUTH_PRIORITIZE_NEW_SESSION = (
    os.getenv("MY_APP_NAME_AUTH_PRIORITIZE_NEW_SESSION", "1").lower() in TRUE_STRS
)

APP_AUTH_BASE_URL = os.getenv("MY_APP_NAME_AUTH_BASE_URL", "http://localhost:3001")
