import os

from zrb import CmdTask, runner

from ..._project import destroy_project
from .._constant import DEPLOYMENT_DIR, PREFER_MICROSERVICES
from .._env import (
    deployment_app_env_file,
    deployment_config_env_file,
    deployment_replica_env,
    pulumi_backend_url_env,
    pulumi_config_passphrase_env,
)
from ._group import snake_zrb_app_name_monolith_group
from .._input import pulumi_stack_input
from ..image._env import image_env

CURRENT_DIR = os.path.dirname(__file__)

destroy_snake_zrb_app_name_monolith = CmdTask(
    icon="💨",
    name="destroy",
    description="Destroy human readable zrb app name monolith deployment",
    group=snake_zrb_app_name_monolith_group,
    inputs=[
        pulumi_stack_input,
    ],
    cwd=DEPLOYMENT_DIR,
    env_files=[
        deployment_config_env_file,
        deployment_app_env_file,
    ],
    envs=[
        pulumi_backend_url_env,
        pulumi_config_passphrase_env,
        image_env,
        deployment_replica_env,
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, "init-pulumi-stack.sh"),
        os.path.join(CURRENT_DIR, "destroy.sh"),
    ],
)

if not PREFER_MICROSERVICES:
    destroy_snake_zrb_app_name_monolith >> destroy_project

runner.register(destroy_snake_zrb_app_name_monolith)
