from zrb import (
    BoolInput, ChoiceInput, IntInput, StrInput, Env, EnvFile,
    HTTPChecker, PortChecker
)
import os

###############################################################################
# Constants
###############################################################################

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
RESOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'kebab-app-name')
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, 'deployment')
APP_DIR = os.path.join(RESOURCE_DIR, 'src')
APP_FRONTEND_DIR = os.path.join(APP_DIR, 'frontend')
APP_FRONTEND_BUILD_DIR = os.path.join(APP_FRONTEND_DIR, 'build')
TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, 'template.env')
SKIP_CONTAINER_EXECUTION = '{{not input.local_snake_app_name}}'
SKIP_SUPPORT_CONTAINER_EXECUTION = ' '.join([
    '{{',
    'not input.local_snake_app_name',
    'or env.get("APP_BROKER_TYPE") not in ["rabbitmq", "kafka"]',
    '}}',
])
SKIP_LOCAL_MONOLITH_EXECUTION = ' '.join([
    '{{',
    'not input.local_snake_app_name',
    'or input.snake_app_name_mode == "microservices"',
    '}}',
])
SKIP_LOCAL_MICROSERVICES_EXECUTION = ' '.join([
    '{{',
    'not input.local_snake_app_name',
    'or input.snake_app_name_mode == "monolith"',
    '}}',
])

###############################################################################
# Checker Task Definitions
###############################################################################

rabbitmq_management_checker = HTTPChecker(
    name='check-rabbitmq-management',
    port='{{env.get("RABBITMQ_MANAGEMENT_HOST_PORT", "15672")}}',
    is_https='{{input.snake_app_name_https}}',
    skip_execution='{{env.get("APP_BROKER_TYPE", "rabbitmq") != "rabbitmq"}}'
)

rabbitmq_checker = PortChecker(
    name='check-rabbitmq',
    port='{{env.get("RABBITMQ_HOST_PORT", "5672")}}',
    skip_execution='{{env.get("APP_BROKER_TYPE", "rabbitmq") != "rabbitmq"}}'
)

redpanda_console_checker = HTTPChecker(
    name='check-redpanda-console',
    method='GET',
    port='{{env.get("REDPANDA_CONSOLE_HOST_PORT", "9000")}}',
    is_https='{{input.snake_app_name_https}}',
    skip_execution='{{env.get("APP_BROKER_TYPE", "rabbitmq") != "kafka"}}'
)

kafka_plaintext_checker = PortChecker(
    name='check-kafka-plaintext',
    port='{{env.get("KAFKA_PLAINTEXT_HOST_PORT", "29092")}}',
    skip_execution='{{env.get("APP_BROKER_TYPE", "rabbitmq") != "kafka"}}'
)

kafka_outside_checker = PortChecker(
    name='check-kafka-outside',
    port='{{env.get("KAFKA_OUTSIDE_HOST_PORT", "9092")}}',
    skip_execution='{{env.get("APP_BROKER_TYPE", "rabbitmq") != "kafka"}}'
)

pandaproxy_plaintext_checker = PortChecker(
    name='check-pandaproxy-plaintext',
    port='{{env.get("PANDAPROXY_PLAINTEXT_HOST_PORT", "29092")}}',
    skip_execution='{{env.get("APP_BROKER_TYPE", "rabbitmq") != "kafka"}}'
)

pandaproxy_outside_checker = PortChecker(
    name='check-pandaproxy-outside',
    port='{{env.get("PANDAPROXY_OUTSIDE_HOST_PORT", "9092")}}',
    skip_execution='{{env.get("APP_BROKER_TYPE", "rabbitmq") != "kafka"}}'
)

app_container_checker = HTTPChecker(
    name='check-kebab-app-name-container',
    host='{{input.snake_app_name_host}}',
    url='/readiness',
    port='{{env.get("HOST_PORT", "httpPort")}}',
    is_https='{{input.snake_app_name_https}}'
)

app_local_checker = HTTPChecker(
    name='check-kebab-app-name',
    host='{{input.snake_app_name_host}}',
    url='/readiness',
    port='{{env.APP_PORT}}',
    is_https='{{input.snake_app_name_https}}'
)

###############################################################################
# Input Definitions
###############################################################################

local_input = BoolInput(
    name='local-kebab-app-name',
    description='Use local "kebab-app-name"',
    prompt='Use local "kebab-app-name"?',
    default=True
)

mode_input = ChoiceInput(
    name='kebab-app-name-mode',
    description='"kebab-app-name" mode',
    prompt='Do you want to run "kebab-app-name" as monolith or microservices?',
    choices=['monolith', 'microservices'],
    default='monolith'
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
# Env file Definitions
###############################################################################

compose_env_file = EnvFile(
    env_file=os.path.join(CURRENT_DIR, 'config', 'docker-compose.env'),
    prefix='CONTAINER_ENV_PREFIX'
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

local_app_port_env = Env(
    name='APP_PORT',
    os_name='ENV_PREFIX_APP_PORT',
    default='httpPort'
)

local_app_broker_type_env = Env(
    name='APP_BROKER_TYPE',
    os_name='ENV_PREFIX_APP_BROKER_TYPE',
    default='rabbitmq'
)

compose_app_broker_type_env = Env(
    name='APP_BROKER_TYPE',
    os_name='CONTAINER_ENV_PREFIX_APP_BROKER_TYPE',
    default='rabbitmq'
)

compose_rabbitmq_host_port_env = Env(
    name='RABBITMQ_HOST_PORT',
    os_name='CONTAINER_ENV_PREFIX_RABBITMQ_HOST_PORT',
    default='5672'
)

compose_rabbitmq_management_host_port_env = Env(
    name='RABBITMQ_MANAGEMENT_HOST_PORT',
    os_name='CONTAINER_ENV_PREFIX_RABBITMQ_MANAGEMENT_HOST_PORT',
    default='15672'
)

compose_redpanda_console_host_port_env = Env(
    name='REDPANDA_CONSOLE_HOST_PORT',
    os_name='CONTAINER_ENV_PREFIX_REDPANDA_CONSOLE_HOST_PORT',
    default='9000'
)

compose_kafka_plaintext_host_port_env = Env(
    name='KAFKA_PLAINTEXT_HOST_PORT',
    os_name='CONTAINER_ENV_PREFIX_KAFKA_PLAINTEXT_HOST_PORT',
    default='29092'
)

compose_kafka_outside_host_port_env = Env(
    name='KAFKA_OUTSIDE_HOST_PORT',
    os_name='CONTAINER_ENV_PREFIX_KAFKA_OUTSIDE_HOST_PORT',
    default='9092'
)

compose_pandaproxy_plaintext_host_port_env = Env(
    name='PANDAPROXY_PLAINTEXT_HOST_PORT',
    os_name='CONTAINER_ENV_PREFIX_PANDAPROXY_PLAINTEXT_HOST_PORT',
    default='29092'
)

compose_pandaproxy_outside_host_port_env = Env(
    name='PANDAPROXY_OUTSIDE_HOST_PORT',
    os_name='CONTAINER_ENV_PREFIX_PANDAPROXY_OUTSIDE_HOST_PORT',
    default='9092'
)

start_container_compose_profile_env = Env(
    name='COMPOSE_PROFILES',
    os_name='',
    default=' '.join([
        '{{',
        '",".join([',
        '  env.get("APP_BROKER_TYPE", "rabbitmq"),',
        '  input.get("snake_app_name_mode", "monolith")',
        '])',
        '}}'
    ])
)

start_support_container_compose_profile_env = Env(
    name='COMPOSE_PROFILES',
    os_name='',
    default=' '.join([
        '{{',
        '",".join([',
        '  env.get("APP_BROKER_TYPE", "rabbitmq"),',
        '])',
        '}}'
    ])
)

all_compose_profile_env = Env(
    name='COMPOSE_PROFILES',
    os_name='',
    default='monolith,microservices,kafka,rabbitmq'
)
