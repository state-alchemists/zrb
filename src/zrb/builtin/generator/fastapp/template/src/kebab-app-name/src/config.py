from typing import List
from helper.conversion import str_to_boolean, str_to_logging_level
import os
import json

app_name = os.getenv('APP_NAME', 'app')
app_logging_level = str_to_logging_level(
    os.getenv('APP_LOGGING_LEVEL', 'INFO')
)
app_broker_type = os.getenv('APP_BROKER_TYPE', 'mock')
app_host = os.getenv('APP_HOST', '0.0.0.0')
app_port = int(os.getenv('APP_PORT', '8080'))
app_reload = str_to_boolean(os.getenv('APP_RELOAD', 'true'))
app_max_not_ready = int(os.getenv('APP_MAX_NOT_READY', '10'))

app_enable_rpc_server: bool = str_to_boolean(os.getenv(
    'APP_ENABLE_RPC_SERVER', 'true'
))

app_enable_message_consumer: bool = str_to_boolean(os.getenv(
    'APP_ENABLE_MESSAGE_CONSUMER', 'true'
))

app_enable_frontend: bool = str_to_boolean(os.getenv(
    'APP_ENABLE_FRONTEND', 'true'
))

app_enable_api: bool = str_to_boolean(os.getenv(
    'APP_ENABLE_API', 'true'
))

app_rmq_connection_string = os.getenv(
    'APP_RMQ_CONNECTION', 'amqp://guest:guest@localhost/'
)

app_kafka_bootstrap_servers = os.getenv(
    'APP_KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'
)
app_kafka_security_protocol = os.getenv(
    'APP_KAFKA_SECURITY_PROTOCOL', 'PLAINTEXT'
)
app_kafka_sasl_mechanism = os.getenv(
    'APP_KAFKA_SASL_MECHANISM', 'SCRAM-SHA-512'
)
app_kafka_sasl_user = os.getenv(
    'APP_KAFKA_SASL_USER', 'admin'
)
app_kafka_sasl_pass = os.getenv(
    'APP_KAFKA_SASL_PASS', 'admin'
)

cors_allow_origins: List[str] = json.loads(os.getenv(
    'APP_CORS_ALLOW_ORIGINS', '["*"]'
))
cors_allow_origin_regex: str = os.getenv(
    'APP_CORS_ALLOW_ORIGIN_REGEX', ''
)
cors_allow_methods: List[str] = json.loads(os.getenv(
    'APP_CORS_ALLOW_METHODS', '["*"]'
))
cors_allow_headers: List[str] = json.loads(os.getenv(
    'APP_CORS_ALLOW_HEADERS', '["*"]'
))
cors_allow_credentials: bool = str_to_boolean(os.getenv(
    'APP_CORS_ALLOW_CREDENTIALS', 'false'
))
cors_expose_headers: bool = str_to_boolean(os.getenv(
    'APP_CORS_EXPOSE_HEADERS', 'false'
))
cors_max_age: int = int(os.getenv(
    'APP_CORS_MAX_AGE', '600'
))
