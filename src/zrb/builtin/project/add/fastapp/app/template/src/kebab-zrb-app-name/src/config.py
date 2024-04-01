import json
import os
from typing import List

from helper.conversion import str_to_boolean, str_to_logging_level

app_src_dir = os.path.dirname(__file__)

zrb_app_name = os.getenv("APP_NAME", "app")
app_logging_level = str_to_logging_level(os.getenv("APP_LOGGING_LEVEL", "INFO"))
app_host = os.getenv("APP_HOST", "0.0.0.0")
app_port = int(os.getenv("APP_PORT", "8080"))
app_reload = str_to_boolean(os.getenv("APP_RELOAD", "true"))
app_max_not_ready = int(os.getenv("APP_MAX_NOT_READY", "10"))

app_enable_otel = str_to_boolean(os.getenv("APP_ENABLE_OTEL", "false"))
app_otel_exporter_otlp_endpoint = os.getenv(
    "APP_OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
)

app_auth_access_token_cookie_key = os.getenv(
    "PUBLIC_AUTH_ACCESS_TOKEN_COOKIE_KEY", "access_token"
)
app_auth_refresh_token_cookie_key = os.getenv(
    "PUBLIC_AUTH_REFRESH_TOKEN_COOKIE_KEY", "refresh_token"
)

app_auth_access_token_type = os.getenv("APP_AUTH_ACCESS_TOKEN_TYPE", "jwt")
app_auth_access_token_expire_seconds = int(
    os.getenv("APP_AUTH_ACCESS_TOKEN_EXPIRE_SECONDS", "300")
)
app_auth_refresh_token_type = os.getenv("APP_AUTH_REFRESH_TOKEN_TYPE", "jwt")
app_auth_refresh_token_expire_seconds = int(
    os.getenv("APP_AUTH_REFRESH_TOKEN_EXPIRE_SECONDS", "86400")
)
app_auth_jwt_token_secret_key = os.getenv("APP_AUTH_JWT_TOKEN_SECRET_KEY", "secret")
app_auth_jwt_token_algorithm = os.getenv("APP_AUTH_JWT_TOKEN_ALGORITHM", "HS256")

app_auth_admin_active = str_to_boolean(os.getenv("APP_AUTH_ADMIN_ACTIVE", "true"))
app_auth_admin_user_id = os.getenv("APP_AUTH_ADMIN_USER_ID", "root")
app_auth_admin_username = os.getenv("APP_AUTH_ADMIN_USERNAME", "admin")
app_auth_admin_password = os.getenv("APP_AUTH_ADMIN_PASSWORD", "admin")
app_auth_admin_email = os.getenv("APP_AUTH_ADMIN_EMAIL", "")
app_auth_admin_phone = os.getenv("APP_AUTH_ADMIN_PHONE", "")
app_auth_guest_user_id = os.getenv("APP_AUTH_GUEST_USER_ID", "guest")
app_auth_guest_username = os.getenv("APP_AUTH_GUEST_USERNAME", "guest")
app_auth_guest_email = os.getenv("APP_AUTH_GUEST_EMAIL", "")
app_auth_guest_phone = os.getenv("APP_AUTH_GUEST_PHONE", "")

app_db_connection = os.getenv("APP_DB_CONNECTION", "sqlite://")
app_db_engine_show_log = str_to_boolean(os.getenv("APP_DB_ENGINE_SHOW_LOG", "false"))
app_db_auto_migrate = str_to_boolean(os.getenv("APP_DB_AUTO_MIGRATE", "true"))

app_broker_type = os.getenv("APP_BROKER_TYPE", "mock")

app_enable_rpc_server: bool = str_to_boolean(os.getenv("APP_ENABLE_RPC_SERVER", "true"))

app_enable_event_handler: bool = str_to_boolean(
    os.getenv("APP_ENABLE_EVENT_HANDLER", "true")
)

app_enable_frontend: bool = str_to_boolean(os.getenv("APP_ENABLE_FRONTEND", "true"))

app_enable_api: bool = str_to_boolean(os.getenv("APP_ENABLE_API", "true"))

app_rmq_connection_string = os.getenv(
    "APP_RMQ_CONNECTION", "amqp://guest:guest@localhost/"
)

app_kafka_bootstrap_servers = os.getenv("APP_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
app_kafka_security_protocol = os.getenv("APP_KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
app_kafka_sasl_mechanism = os.getenv("APP_KAFKA_SASL_MECHANISM", "SCRAM-SHA-512")
app_kafka_sasl_user = os.getenv("APP_KAFKA_SASL_USER", "admin")
app_kafka_sasl_pass = os.getenv("APP_KAFKA_SASL_PASS", "admin")

app_cors_allow_origins: List[str] = json.loads(
    os.getenv("APP_CORS_ALLOW_ORIGINS", '["*"]')
)
app_cors_allow_origin_regex: str = os.getenv("APP_CORS_ALLOW_ORIGIN_REGEX", "")
app_cors_allow_methods: List[str] = json.loads(
    os.getenv("APP_CORS_ALLOW_METHODS", '["*"]')
)
app_cors_allow_headers: List[str] = json.loads(
    os.getenv("APP_CORS_ALLOW_HEADERS", '["*"]')
)
app_cors_allow_credentials: bool = str_to_boolean(
    os.getenv("APP_CORS_ALLOW_CREDENTIALS", "false")
)
app_cors_expose_headers: bool = str_to_boolean(
    os.getenv("APP_CORS_EXPOSE_HEADERS", "false")
)
app_cors_max_age: int = int(os.getenv("APP_CORS_MAX_AGE", "600"))
app_enable_auth_module = str_to_boolean(os.getenv("APP_ENABLE_AUTH_MODULE", "true"))
app_enable_log_module = str_to_boolean(os.getenv("APP_ENABLE_LOG_MODULE", "true"))

public_brand = os.getenv("PUBLIC_BRAND", "PascalZrbAppName")
public_title = os.getenv("PUBLIC_TITLE", "PascalZrbAppName")
public_auth_access_token_cookie_key = os.getenv(
    "PUBLIC_AUTH_ACCESS_TOKEN_COOKIE_KEY", "access_token"
)
public_auth_refresh_token_cookie_key = os.getenv(
    "PUBLIC_AUTH_REFRESH_TOKEN_COOKIE_KEY", "refresh_token"
)
