import os

from zrb import CmdTask, runner

from .._project import deploy_project
from ._constant import DEPLOYMENT_DIR
from ._env import (
    deployment_app_env_file,
    deployment_config_env_file,
    deployment_replica_env,
    pulumi_backend_url_env,
    pulumi_config_passphrase_env,
)
from ._group import snake_zrb_app_name_group
from ._input import pulumi_stack_input, replica_input
from .image import push_snake_zrb_app_name_image
from .image._env import image_env
from .image._input import image_input

_CURRENT_DIR = os.path.dirname(__file__)

deploy_snake_zrb_app_name = CmdTask(
    icon="🚧",
    name="deploy",
    description="Deploy human readable zrb app name",
    group=snake_zrb_app_name_group,
    inputs=[
        image_input,
        replica_input,
        pulumi_stack_input,
    ],
    upstreams=[push_snake_zrb_app_name_image],
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
        os.path.join(_CURRENT_DIR, "init-pulumi-stack.sh"),
        os.path.join(_CURRENT_DIR, "deploy.sh"),
    ],
)

deploy_snake_zrb_app_name >> deploy_project

runner.register(deploy_snake_zrb_app_name)
