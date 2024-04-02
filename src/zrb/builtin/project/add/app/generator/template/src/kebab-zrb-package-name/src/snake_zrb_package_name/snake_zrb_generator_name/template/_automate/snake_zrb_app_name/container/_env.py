import os

from zrb import Env, EnvFile

from .._constant import RESOURCE_DIR

compose_env_file = EnvFile(
    path=os.path.join(RESOURCE_DIR, "docker-compose.env"),
    prefix="CONTAINER_ZRB_ENV_PREFIX",
)

host_port_env = Env(
    name="HOST_PORT",
    os_name="CONTAINER_ZRB_ENV_PREFIX_HOST_PORT",
    default="zrbAppHttpPort",
)
