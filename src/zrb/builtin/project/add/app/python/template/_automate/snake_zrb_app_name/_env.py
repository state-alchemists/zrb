from zrb import EnvFile
from ._constant import APP_TEMPLATE_ENV_FILE_NAME, DEPLOYMENT_TEMPLATE_ENV_FILE_NAME

deployment_app_env_file = EnvFile(
    path=APP_TEMPLATE_ENV_FILE_NAME, prefix="DEPLOYMENT_APP_ZRB_ENV_PREFIX"
)

deployment_config_env_file = EnvFile(
    path=DEPLOYMENT_TEMPLATE_ENV_FILE_NAME, prefix="DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX"
)
