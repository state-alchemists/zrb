from zrb import Env
from ..common import image_env

compose_env_prefix = 'CONTAINER_ENV_PREFIX'
compose_envs = [
    image_env,
    Env(
        name='APP_BROKER_TYPE',
        os_name='CONTAINER_ENV_PREFIX_APP_BROKER_TYPE',
        default='rabbitmq'
    ),
    Env(
        name='APP_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_APP_HOST_PORT',
        default='httpPort'
    ),
    Env(
        name='RABBITMQ_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_RABBITMQ_HOST_PORT',
        default='5672'
    ),
    Env(
        name='RABBITMQ_MANAGEMENT_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_RABBITMQ_MANAGEMENT_HOST_PORT',
        default='15672'
    ),
    Env(
        name='REDPANDA_CONSOLE_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_REDPANDA_CONSOLE_HOST_PORT',
        default='9000'
    ),
    Env(
        name='KAFKA_PLAINTEXT_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_KAFKA_PLAINTEXT_HOST_PORT',
        default='29092'
    ),
    Env(
        name='KAFKA_OUTSIDE_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_KAFKA_OUTSIDE_HOST_PORT',
        default='9092'
    ),
    Env(
        name='PANDAPROXY_PLAINTEXT_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_PANDAPROXY_PLAINTEXT_HOST_PORT',
        default='29092'
    ),
    Env(
        name='PANDAPROXY_OUTSIDE_HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_PANDAPROXY_OUTSIDE_HOST_PORT',
        default='9092'
    ),
]
