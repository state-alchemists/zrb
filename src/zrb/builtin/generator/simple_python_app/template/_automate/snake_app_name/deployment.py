from typing import List
from zrb import Input, CmdTask, Env, EnvFile, runner
from zrb.builtin._group import project_group
from .image import push_snake_app_name_image
from .common import (
    CURRENT_DIR, DEPLOYMENT_DIR, TEMPLATE_ENV_FILE_NAME,
    image_input, pulumi_stack_input, replica_input, image_env,
    deployment_replica_env, pulumi_backend_url_env,
    pulumi_config_passphrase_env
)
import os

app_env_file = EnvFile(
    env_file=TEMPLATE_ENV_FILE_NAME, prefix='DEPLOYMENT_APP_ENV_PREFIX'
)

deployment_inputs: List[Input] = [
    image_input,
    replica_input,
    pulumi_stack_input,
]

deployment_envs: List[Env] = [
    pulumi_backend_url_env,
    pulumi_config_passphrase_env,
    image_env,
    deployment_replica_env,
]

deploy_snake_app_name_image = CmdTask(
    icon='🚧',
    name='deploy-kebab-app-name-image',
    description='Deploy human readable app name',
    group=project_group,
    inputs=deployment_inputs,
    upstreams=[push_snake_app_name_image],
    cwd=DEPLOYMENT_DIR,
    env_files=[app_env_file],
    envs=deployment_envs,
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'pulumi-up.sh'),
)
runner.register(deploy_snake_app_name_image)

remove_snake_app_name_deployment = CmdTask(
    icon='💨',
    name='remove-kebab-app-name-deployment',
    description='Remove human readable app name deployment',
    group=project_group,
    inputs=deployment_inputs,
    cwd=DEPLOYMENT_DIR,
    env_files=[app_env_file],
    envs=deployment_envs,
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'pulumi-destroy.sh'),
)
runner.register(remove_snake_app_name_deployment)
