from zrb import Env, EnvFile

from ._constant import (
    APP_TEMPLATE_ENV_FILE_NAME,
    DEPLOYMENT_DIR,
    DEPLOYMENT_TEMPLATE_ENV_FILE_NAME,
)

deployment_app_env_file = EnvFile(
    path=APP_TEMPLATE_ENV_FILE_NAME, prefix="DEPLOYMENT_APP_ZRB_ENV_PREFIX"
)

deployment_config_env_file = EnvFile(
    path=DEPLOYMENT_TEMPLATE_ENV_FILE_NAME, prefix="DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX"
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
