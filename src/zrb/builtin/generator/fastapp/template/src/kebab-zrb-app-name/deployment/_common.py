import copy
import os
import re
from typing import List, Mapping

import jsons
from dotenv import dotenv_values

NON_ALPHA_NUM = re.compile(r"[^a-zA-Z0-9]+")
CURRENT_DIR: str = os.path.dirname(__file__)
MODE: str = os.getenv("MODE", "monolith")
NAMESPACE: str = os.getenv("NAMESPACE", "default")

ENABLE_MONITORING: bool = os.getenv("ENABLE_MONITORING", "0") in [
    "1",
    "true",
    "True",
    "Yes",
    "yes",
    "Y",
    "y",
]

MODULE_JSON_STR: str = os.getenv("MODULES", "[]")
MODULES: List[str] = jsons.loads(MODULE_JSON_STR)

APP_DIR: str = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
TEMPLATE_ENV_FILE_NAME: str = os.path.join(APP_DIR, "template.env")
TEMPLATE_ENV_MAP: Mapping[str, str] = {
    key: os.getenv(key, default_value)
    for key, default_value in dotenv_values(TEMPLATE_ENV_FILE_NAME).items()
}

BROKER_TYPE: str = os.getenv("BROKER_TYPE", "")
if BROKER_TYPE == "":
    BROKER_TYPE = TEMPLATE_ENV_MAP.get("APP_BROKER_TYPE", "rabbitmq")

RABBITMQ_AUTH_USERNAME: str = os.getenv("RABBITMQ_AUTH_USERNAME", "root")
RABBITMQ_AUTH_PASSWORD: str = os.getenv("RABBITMQ_AUTH_PASSWORD", "toor")

REDPANDA_AUTH_SASL_ENABLED: bool = (
    os.getenv("REDPANDA_AUTH_SASL_ENABLED", "true").lower() == "true"
)
REDPANDA_AUTH_MECHANISM: str = os.getenv("REDPANDA_AUTH_MECHANISM", "SCRAM-SHA-512")
REDPANDA_AUTH_USER_NAME: str = os.getenv("REDPANDA_AUTH_USER_NAME", "root")
REDPANDA_AUTH_USER_PASSWORD: str = os.getenv("REDPANDA_AUTH_USER_PASSWORD", "toor")

POSTGRESQL_AUTH_POSTGRES_PASSWORD: str = os.getenv("POSTGRESQL_AUTH_POSTGRES_PASSWORD")
POSTGRESQL_AUTH_USERNAME: str = os.getenv("POSTGRESQL_AUTH_USERNAME", "root")
POSTGRESQL_AUTH_PASSWORD: str = os.getenv("POSTGRESQL_AUTH_PASSWORD", "toor")
POSTGRESQL_DB: str = os.getenv("POSTGRESQL_DB", "snake_zrb_app_name")

SIGNOZ_CLICKHOUSE_NAMESPACE: str = os.getenv("SIGNOZ_CLICKHOUSE_NAMESPACE", NAMESPACE)
SIGNOZ_CLICKHOUSE_USER: str = os.getenv("SIGNOZ_CLICKHOUSE_USER", "root")
SIGNOZ_CLICKHOUSE_PASSWORD: str = os.getenv("SIGNOZ_CLICKHOUSE_PASSWORD", "toor")


def get_app_monolith_env_map(
    template_env_map: Mapping[str, str], modules: List[str]
) -> Mapping[str, str]:
    env_map = copy.deepcopy(template_env_map)
    env_map[
        "APP_RMQ_CONNECTION"
    ] = f"amqp://{RABBITMQ_AUTH_USERNAME}:{RABBITMQ_AUTH_PASSWORD}@rabbitmq"  # noqa
    env_map["APP_KAFKA_BOOTSTRAP_SERVERS"] = "redpanda:9092"
    env_map["APP_KAFKA_SASL_MECHANISM"] = REDPANDA_AUTH_MECHANISM
    env_map["APP_KAFKA_SASL_USER"] = REDPANDA_AUTH_USER_NAME
    env_map["APP_KAFKA_SASL_PASSWORD"] = REDPANDA_AUTH_USER_PASSWORD
    env_map[
        "APP_DB_CONNECTION"
    ] = f"postgresql+psycopg2://{POSTGRESQL_AUTH_USERNAME}:{POSTGRESQL_AUTH_PASSWORD}@postgresql:5432/{POSTGRESQL_DB}"  # noqa
    for module_name in modules:
        env_name = get_module_flag_env_name(module_name)
        env_map[env_name] = "true"
    env_map["APP_ENABLE_EVENT_HANDLER"] = "true"
    env_map["APP_ENABLE_RPC_SERVER"] = "true"
    env_map["APP_ENABLE_FRONTEND"] = "true"
    env_map["APP_ENABLE_API"] = "true"
    env_map["APP_ENABLE_OTEL"] = "true" if ENABLE_MONITORING else "false"
    env_map[
        "APP_OTEL_EXPORTER_OTLP_ENDPOINT"
    ] = "http://signoz-otel-collector:4317"  # noqa
    return env_map


def get_app_gateway_env_map(
    template_env_map: Mapping[str, str], modules: List[str]
) -> Mapping[str, str]:
    env_map = get_app_monolith_env_map(template_env_map, modules)
    for module_name in modules:
        env_name = get_module_flag_env_name(module_name)
        env_map[env_name] = "true"
    env_map["APP_ENABLE_EVENT_HANDLER"] = "false"
    env_map["APP_ENABLE_RPC_SERVER"] = "false"
    env_map["APP_ENABLE_FRONTEND"] = "true"
    env_map["APP_ENABLE_API"] = "true"
    env_map["APP_DB_AUTO_MIGRATE"] = "false"
    return env_map


def get_app_service_env_map(
    template_env_map: Mapping[str, str], modules: List[str], current_module: str
) -> Mapping[str, str]:
    env_map = get_app_monolith_env_map(template_env_map, modules)
    for module_name in modules:
        env_name = get_module_flag_env_name(module_name)
        if module_name == current_module:
            env_map[env_name] = "true"
            continue
        env_map[env_name] = "false"
    env_map["APP_ENABLE_EVENT_HANDLER"] = "true"
    env_map["APP_ENABLE_RPC_SERVER"] = "true"
    env_map["APP_ENABLE_FRONTEND"] = "false"
    env_map["APP_ENABLE_API"] = "false"
    return env_map


def get_module_flag_env_name(module_name: str) -> str:
    upper_snake_module_name = to_snake_case(module_name).upper()
    return f"APP_ENABLE_{upper_snake_module_name}_MODULE"


def to_kebab_case(text: str) -> str:
    text = to_alphanum(text)
    return "-".join([x.lower() for x in text.split(" ")])


def to_snake_case(text: str) -> str:
    text = to_alphanum(text)
    return "_".join([x.lower() for x in text.split(" ")])


def to_alphanum(text: str) -> str:
    return NON_ALPHA_NUM.sub(" ", text)
