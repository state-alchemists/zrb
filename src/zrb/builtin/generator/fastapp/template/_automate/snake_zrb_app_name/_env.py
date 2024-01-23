import jsons

from zrb import Env

from ._config import DEPLOYMENT_DIR, MODULES

app_enable_otel_env = Env(
    name="APP_ENABLE_OTEL",
    default='{{ "1" if input.enable_snake_zrb_app_name_monitoring else "0" }}',
)

image_env = Env(
    name="IMAGE",
    os_name="CONTAINER_ZRB_ENV_PREFIX_IMAGE",
    default="{{input.snake_zrb_app_name_image}}",
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

deployment_modules_env = Env(
    name="MODULES",
    os_name="DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX_MODULES",
    default=jsons.dumps(MODULES),
)

deployment_mode_env = Env(
    name="MODE",
    os_name="DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX_MODE",
    default="{{input.snake_zrb_app_name_deploy_mode}}",
)

deployment_enable_monitoring_env = Env(
    name="ENABLE_MONITORING",
    os_name="DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX_ENABLE_MONITORING",
    default="{{ 1 if input.enable_snake_zrb_app_name_monitoring else 0 }}",
)
