from zrb import Env, EnvFile
from ..common import TEMPLATE_ENV_FILE_NAME

app_env_file = EnvFile(env_file=TEMPLATE_ENV_FILE_NAME, prefix='ENV_PREFIX')
app_envs = [
    Env(
        name='APP_PORT',
        os_name='ENV_PREFIX_APP_PORT',
        default='httpPort'
    ),
    Env(
        name='APP_BROKER_TYPE',
        os_name='ENV_PREFIX_APP_BROKER_TYPE',
        default='rabbitmq'
    )
]
