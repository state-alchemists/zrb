from typing import Mapping
from dotenv import dotenv_values
import os

CURRENT_DIR: str = os.path.dirname(__file__)
MODE = os.getenv('MODE', 'monolith')
NAMESPACE = os.getenv('NAMESPACE', 'default')
APP_DIR: str = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'src'))

TEMPLATE_ENV_FILE_NAME: str = os.path.join(APP_DIR, 'template.env')
TEMPLATE_ENV_MAP: Mapping[str, str] = {
    key: os.getenv(key, default_value)
    for key, default_value in dotenv_values(TEMPLATE_ENV_FILE_NAME).items()
}
BROKER_TYPE = TEMPLATE_ENV_MAP.get('APP_BROKER_TYPE', 'rabbitmq')

RABBITMQ_AUTH_USERNAME: str = os.getenv('RABBITMQ_AUTH_USERNAME', 'root')
RABBITMQ_AUTH_PASSWORD: str = os.getenv('RABBITMQ_AUTH_PASSWORD', 'toor')

REDPANDA_AUTH_SASL_ENABLED: bool = os.getenv('REDPANDA_AUTH_SASL_ENABLED', 'true').lower() == 'true'  # noqa
REDPANDA_AUTH_MECHANISM: str = os.getenv('REDPANDA_AUTH_MECHANISM', 'SCRAM-SHA-512')  # noqa
REDPANDA_AUTH_USER_NAME: str = os.getenv('REDPANDA_AUTH_USER_NAME')
REDPANDA_AUTH_USER_PASSWORD: str = os.getenv('REDPANDA_AUTH_USER_PASSWORD')

POSTGRESQL_AUTH_POSTGRES_PASSWORD: str = os.getenv('POSTGRESQL_AUTH_POSTGRES_PASSWORD')  # noqa
POSTGRESQL_AUTH_USERNAME: str = os.getenv('POSTGRESQL_AUTH_USERNAME')
POSTGRESQL_AUTH_PASSWORD: str = os.getenv('POSTGRESQL_AUTH_PASSWORD')
