from zrb import BoolInput, IntInput, StrInput, Env
import os

###############################################################################
# Constants
###############################################################################

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
RESOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'kebab-app-name')
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, 'deployment')
APP_DIR = os.path.join(RESOURCE_DIR, 'src')
TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, 'template.env')

###############################################################################
# Input Definitions
###############################################################################

local_input = BoolInput(
    name='local-kebab-app-name',
    description='Use local "kebab-app-name"',
    prompt='Use local "kebab-app-name"?',
    default=True
)

https_input = BoolInput(
    name='kebab-app-name-https',
    description='Whether "kebab-app-name" run on HTTPS',
    prompt='Is "kebab-app-name" run on HTTPS?',
    default=False
)

host_input = StrInput(
    name='kebab-app-name-host',
    description='Hostname of "kebab-app-name"',
    prompt='Hostname of "kebab-app-name"',
    default='localhost'
)

image_input = StrInput(
    name='kebab-app-name-image',
    description='Image name of "kebab-app-name"',
    prompt='Image name of "kebab-app-name"',
    default='app-image-name:latest'
)

replica_input = IntInput(
    name='kebab-app-name-replica',
    description='Replica of "kebab-app-name"',
    prompt='Replica of "kebab-app-name"',
    default=1,
)

pulumi_stack_input = StrInput(
    name='kebab-app-name-pulumi-stack',
    description='Pulumi stack name for "kebab-app-name"',
    prompt='Pulumi stack name for "kebab-app-name"',
    default=os.getenv('ZRB_ENV', 'dev')
)

###############################################################################
# Env Definitions
###############################################################################

image_env = Env(
    name='IMAGE',
    os_name='CONTAINER_ENV_PREFIX_IMAGE',
    default='{{input.snake_app_name_image}}'
)

pulumi_backend_url_env = Env(
    name='PULUMI_BACKEND_URL',
    os_name='PULUMI_ENV_PREFIX_BACKEND_URL',
    default=f'file://{DEPLOYMENT_DIR}/state'
)

pulumi_config_passphrase_env = Env(
    name='PULUMI_CONFIG_PASSPHRASE',
    os_name='PULUMI_ENV_PREFIX_CONFIG_PASSPHRASE',
    default='secret'
)

deployment_replica_env = Env(
    name='REPLICA',
    os_name='DEPLOYMENT_ENV_PREFIX',
    default='{{input.snake_app_name_replica}}'
)
