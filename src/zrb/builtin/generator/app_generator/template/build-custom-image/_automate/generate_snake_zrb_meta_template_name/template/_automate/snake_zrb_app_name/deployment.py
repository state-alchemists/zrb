from zrb import CmdTask, Env, EnvFile, IntInput, StrInput, runner
from zrb.builtin.group import project_group
from .image import push_snake_zrb_app_name_image, image_input, image_env
from ._common import (
    CURRENT_DIR, DEPLOYMENT_DIR, APP_TEMPLATE_ENV_FILE_NAME,
    DEPLOYMENT_TEMPLATE_ENV_FILE_NAME
)
import os

###############################################################################
# Input Definitions
###############################################################################

replica_input = IntInput(
    name='kebab-zrb-app-name-replica',
    description='Replica of "kebab-zrb-app-name"',
    prompt='Replica of "kebab-zrb-app-name"',
    default=1,
)

pulumi_stack_input = StrInput(
    name='kebab-zrb-app-name-pulumi-stack',
    description='Pulumi stack name for "kebab-zrb-app-name"',
    prompt='Pulumi stack name for "kebab-zrb-app-name"',
    default=os.getenv('ZRB_ENV', 'dev')
)

###############################################################################
# Env File Definitions
###############################################################################

deployment_app_env_file = EnvFile(
    env_file=APP_TEMPLATE_ENV_FILE_NAME,
    prefix='DEPLOYMENT_APP_ZRB_ENV_PREFIX'
)

deployment_config_env_file = EnvFile(
    env_file=DEPLOYMENT_TEMPLATE_ENV_FILE_NAME,
    prefix='DEPLOYMENT_CONFIG_ZRB_ENV_PREFIX'
)

###############################################################################
# Env Definitions
###############################################################################

pulumi_backend_url_env = Env(
    name='PULUMI_BACKEND_URL',
    os_name='PULUMI_ZRB_ENV_PREFIX_BACKEND_URL',
    default=f'file://{DEPLOYMENT_DIR}/state'
)

pulumi_config_passphrase_env = Env(
    name='PULUMI_CONFIG_PASSPHRASE',
    os_name='PULUMI_ZRB_ENV_PREFIX_CONFIG_PASSPHRASE',
    default='secret'
)

deployment_replica_env = Env(
    name='REPLICA',
    os_name='DEPLOYMENT_ZRB_ENV_PREFIX',
    default='{{input.snake_zrb_app_name_replica}}'
)

###############################################################################
# Task Definitions
###############################################################################

deploy_snake_zrb_app_name = CmdTask(
    icon='🚧',
    name='deploy-kebab-zrb-app-name',
    description='Deploy human readable zrb app name',
    group=project_group,
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
        os.path.join(CURRENT_DIR, 'cmd', 'pulumi-init-stack.sh'),
        os.path.join(CURRENT_DIR, 'cmd', 'pulumi-up.sh'),
    ]
)
runner.register(deploy_snake_zrb_app_name)

destroy_snake_zrb_app_name = CmdTask(
    icon='💨',
    name='destroy-kebab-zrb-app-name',
    description='Remove human readable zrb app name deployment',
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
        deployment_replica_env,
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, 'cmd', 'pulumi-init-stack.sh'),
        os.path.join(CURRENT_DIR, 'cmd', 'pulumi-destroy.sh'),
    ]
)
runner.register(destroy_snake_zrb_app_name)
