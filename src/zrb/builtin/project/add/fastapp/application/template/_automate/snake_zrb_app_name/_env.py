from zrb import Env, EnvFile

from ._constant import (
    APP_TEMPLATE_ENV_FILE_NAME,
    DEPLOYMENT_DIR,
    DEPLOYMENT_TEMPLATE_ENV_FILE_NAME,
)

app_env_file = EnvFile(path=APP_TEMPLATE_ENV_FILE_NAME, prefix="ZRB_ENV_PREFIX")

app_enable_otel_env = Env(
    name="APP_ENABLE_OTEL",
    default='{{ "1" if input.enable_snake_zrb_app_name_monitoring else "0" }}',
)

image_env = Env(
    name="IMAGE",
    os_name="CONTAINER_ZRB_ENV_PREFIX_IMAGE",
    default="{{input.snake_zrb_app_name_image}}",
)

deployment_app_env_file = EnvFile(
    path=APP_TEMPLATE_ENV_FILE_NAME, prefix="DEPLOYMENT_APP_ZRB_ENV_PREFIX"
)

deployment_config_env_file = EnvFile(
    path=DEPLOYMENT_TEMPLATE_ENV_FILE_NAME, prefix="DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX"
)

deployment_enable_monitoring_env = Env(
    name="ENABLE_MONITORING",
    os_name="DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX_ENABLE_MONITORING",
    default="{{ 1 if input.enable_snake_zrb_app_name_monitoring else 0 }}",
)

pulumi_backend_url_env = Env(
    name="PULUMI_BACKEND_URL",
    os_name="PULUMI_ZRB_ENV_PREFIX_BACKEND_URL",
    default=f"file://{DEPLOYMENT_DIR}/state",
)

pulumi_config_passphrase_env = Env(
    name="PULUMI_CONFIG_PASSPHRASE",
    os_name="PULUMI_ZRB_ENV_PREFIX_CONFIG_PASSPHRASE",
    default="secret",
)

deployment_replica_env = Env(
    name="REPLICA",
    os_name="DEPLOYMENT_ZRB_ENV_PREFIX",
    default="{{input.snake_zrb_app_name_replica}}",
)
