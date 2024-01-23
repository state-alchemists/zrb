import os

from zrb import CmdTask, runner
from zrb.builtin.group import project_group

from ._config import CURRENT_DIR, DEPLOYMENT_DIR
from ._env import (
    deployment_enable_monitoring_env,
    deployment_mode_env,
    deployment_modules_env,
    image_env,
    pulumi_backend_url_env,
    pulumi_config_passphrase_env,
)
from ._env_file import deployment_app_env_file, deployment_config_env_file
from ._input import (
    deploy_mode_input,
    enable_monitoring_input,
    image_input,
    pulumi_stack_input,
)
from .image import push_snake_zrb_app_name_image

###############################################################################
# ⚙️ deploy-kebab-zrb-task-name
###############################################################################

deploy_snake_zrb_app_name = CmdTask(
    icon="🚧",
    name="deploy-kebab-zrb-app-name",
    description="Deploy human readable zrb app name",
    group=project_group,
    inputs=[
        image_input,
        pulumi_stack_input,
        deploy_mode_input,
        enable_monitoring_input,
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
        deployment_modules_env,
        deployment_mode_env,
        deployment_enable_monitoring_env,
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "pulumi-init-stack.sh"),
        os.path.join(CURRENT_DIR, "cmd", "pulumi-up.sh"),
    ],
)
runner.register(deploy_snake_zrb_app_name)

###############################################################################
# ⚙️ destroy-kebab-zrb-task-name
###############################################################################

destroy_snake_zrb_app_name = CmdTask(
    icon="💨",
    name="destroy-kebab-zrb-app-name",
    description="Remove human readable zrb app name deployment",
    group=project_group,
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
        deployment_modules_env,
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "pulumi-init-stack.sh"),
        os.path.join(CURRENT_DIR, "cmd", "pulumi-destroy.sh"),
    ],
)
runner.register(destroy_snake_zrb_app_name)
