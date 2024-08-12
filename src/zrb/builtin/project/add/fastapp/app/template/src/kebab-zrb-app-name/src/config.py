import json
import os

from helper.conversion import str_to_boolean, str_to_logging_level

APP_SRC_DIR = os.path.dirname(__file__)

APP_NAME = os.getenv("APP_NAME", "app")
APP_BRAND = os.getenv("PUBLIC_BRAND", "PascalZrbAppName")
APP_TITLE = os.getenv("PUBLIC_TITLE", "PascalZrbAppName")

APP_LOGGING_LEVEL = str_to_logging_level(os.getenv("APP_LOGGING_LEVEL", "INFO"))
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8080"))
APP_RELOAD = str_to_boolean(os.getenv("APP_RELOAD", "true"))
APP_MAX_NOT_READY = int(os.getenv("APP_MAX_NOT_READY", "10"))

APP_ENABLE_OTEL = str_to_boolean(os.getenv("APP_ENABLE_OTEL", "false"))
APP_OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
    "APP_OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
)

APP_AUTH_ACCESS_TOKEN_COOKIE_KEY = os.getenv(
    "APP_AUTH_ACCESS_TOKEN_COOKIE_KEY", "access_token"
)
APP_AUTH_REFRESH_TOKEN_COOKIE_KEY = os.getenv(
    "APP_AUTH_REFRESH_TOKEN_COOKIE_KEY", "refresh_token"
)

APP_AUTH_ACCESS_TOKEN_TYPE = os.getenv("APP_AUTH_ACCESS_TOKEN_TYPE", "jwt")
APP_AUTH_ACCESS_TOKEN_EXPIRE_SECONDS = int(
    os.getenv("APP_AUTH_ACCESS_TOKEN_EXPIRE_SECONDS", "300")
)
APP_AUTH_REFRESH_TOKEN_TYPE = os.getenv("APP_AUTH_REFRESH_TOKEN_TYPE", "jwt")
APP_AUTH_REFRESH_TOKEN_EXPIRE_SECONDS = int(
    os.getenv("APP_AUTH_REFRESH_TOKEN_EXPIRE_SECONDS", "86400")
)
APP_AUTH_JWT_TOKEN_SECRET_KEY = os.getenv("APP_AUTH_JWT_TOKEN_SECRET_KEY", "secret")
APP_AUTH_JWT_TOKEN_ALGORITHM = os.getenv("APP_AUTH_JWT_TOKEN_ALGORITHM", "HS256")

APP_AUTH_ADMIN_ACTIVE = str_to_boolean(os.getenv("APP_AUTH_ADMIN_ACTIVE", "true"))
APP_AUTH_ADMIN_USER_ID = os.getenv("APP_AUTH_ADMIN_USER_ID", "root")
APP_AUTH_ADMIN_USERNAME = os.getenv("APP_AUTH_ADMIN_USERNAME", "admin")
APP_AUTH_ADMIN_PASSWORD = os.getenv("APP_AUTH_ADMIN_PASSWORD", "admin")
APP_AUTH_ADMIN_EMAIL = os.getenv("APP_AUTH_ADMIN_EMAIL", "")
APP_AUTH_ADMIN_PHONE = os.getenv("APP_AUTH_ADMIN_PHONE", "")
APP_AUTH_GUEST_USER_ID = os.getenv("APP_AUTH_GUEST_USER_ID", "guest")
APP_AUTH_GUEST_USERNAME = os.getenv("APP_AUTH_GUEST_USERNAME", "guest")
APP_AUTH_GUEST_EMAIL = os.getenv("APP_AUTH_GUEST_EMAIL", "")
APP_AUTH_GUEST_PHONE = os.getenv("APP_AUTH_GUEST_PHONE", "")

APP_DB_CONNECTION = os.getenv("APP_DB_CONNECTION", "sqlite://")
APP_DB_ENGINE_SHOW_LOG = str_to_boolean(os.getenv("APP_DB_ENGINE_SHOW_LOG", "false"))
APP_DB_AUTO_MIGRATE = str_to_boolean(os.getenv("APP_DB_AUTO_MIGRATE", "true"))
APP_DB_POOL_PRE_PING = str_to_boolean(os.getenv("APP_DB_POOL_PRE_PING", "true"))
APP_DB_POOL_SIZE = int(os.getenv("APP_DB_POOL_SIZE", "20"))
APP_DB_POOL_MAX_OVERFLOW = int(os.getenv("APP_DB_POOL_MAX_OVERFLOW", "0"))


APP_BROKER_TYPE = os.getenv("APP_BROKER_TYPE", "mock")

APP_ENABLE_RPC_SERVER: bool = str_to_boolean(os.getenv("APP_ENABLE_RPC_SERVER", "true"))

APP_ENABLE_EVENT_HANDLER: bool = str_to_boolean(
    os.getenv("APP_ENABLE_EVENT_HANDLER", "true")
)

APP_ENABLE_FRONTEND: bool = str_to_boolean(os.getenv("APP_ENABLE_FRONTEND", "true"))

APP_ENABLE_API: bool = str_to_boolean(os.getenv("APP_ENABLE_API", "true"))

APP_RMQ_CONNECTION_STRING = os.getenv(
    "APP_RMQ_CONNECTION", "amqp://guest:guest@localhost/"
)

APP_KAFKA_BOOTSTRAP_SERVERS = os.getenv("APP_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
APP_KAFKA_SECURITY_PROTOCOL = os.getenv("APP_KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
APP_KAFKA_SASL_MECHANISM = os.getenv("APP_KAFKA_SASL_MECHANISM", "SCRAM-SHA-512")
APP_KAFKA_SASL_USER = os.getenv("APP_KAFKA_SASL_USER", "admin")
APP_KAFKA_SASL_PASS = os.getenv("APP_KAFKA_SASL_PASS", "admin")

APP_CORS_ALLOW_ORIGINS: list[str] = json.loads(
    os.getenv("APP_CORS_ALLOW_ORIGINS", '["*"]')
)
APP_CORS_ALLOW_ORIGIN_REGEX: str = os.getenv("APP_CORS_ALLOW_ORIGIN_REGEX", "")
APP_CORS_ALLOW_METHODS: list[str] = json.loads(
    os.getenv("APP_CORS_ALLOW_METHODS", '["*"]')
)
APP_CORS_ALLOW_HEADERS: list[str] = json.loads(
    os.getenv("APP_CORS_ALLOW_HEADERS", '["*"]')
)
APP_CORS_ALLOW_CREDENTIALS: bool = str_to_boolean(
    os.getenv("APP_CORS_ALLOW_CREDENTIALS", "false")
)
APP_CORS_EXPOSE_HEADERS: bool = str_to_boolean(
    os.getenv("APP_CORS_EXPOSE_HEADERS", "false")
)
APP_CORS_MAX_AGE: int = int(os.getenv("APP_CORS_MAX_AGE", "600"))
APP_ENABLE_AUTH_MODULE = str_to_boolean(os.getenv("APP_ENABLE_AUTH_MODULE", "true"))
APP_ENABLE_LOG_MODULE = str_to_boolean(os.getenv("APP_ENABLE_LOG_MODULE", "true"))
