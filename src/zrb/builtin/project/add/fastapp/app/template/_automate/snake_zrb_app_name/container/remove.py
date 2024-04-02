from zrb import DockerComposeTask, runner

from ..._project import remove_project_containers
from .._constant import RESOURCE_DIR
from ..image._env import image_env
from ._env import compose_env_file
from ._group import snake_zrb_app_name_container_group
from ._helper import activate_all_compose_profile
from ._service_config import snake_zrb_app_name_service_configs

remove_snake_zrb_app_name_container = DockerComposeTask(
    icon="💨",
    name="remove",
    description="Remove human readable zrb app name container",
    group=snake_zrb_app_name_container_group,
    cwd=RESOURCE_DIR,
    setup_cmd=activate_all_compose_profile,
    compose_cmd="down",
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=snake_zrb_app_name_service_configs,
    env_files=[compose_env_file],
    envs=[image_env],
)

remove_snake_zrb_app_name_container >> remove_project_containers

runner.register(remove_snake_zrb_app_name_container)
