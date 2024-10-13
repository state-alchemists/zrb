from zrb import DockerComposeMaker

from .._constant import RESOURCE_DIR
from ..image._env import image_env
from ._env import compose_env_file, host_port_env
from ._service_config import snake_zrb_app_name_service_config

make_snake_zrb_app_name_compose_file = DockerComposeMaker(
    icon="🐳",
    name="make-kebab-zrb-app-name-compose-file",
    cwd=RESOURCE_DIR,
    compose_service_configs={"kebab-zrb-app-name": snake_zrb_app_name_service_config},
    env_files=[compose_env_file],
    envs=[
        image_env,
        host_port_env,
    ],
)
