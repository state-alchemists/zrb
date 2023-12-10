from typing import Mapping
from zrb import Env, ServiceConfig, EnvFile
from zrb.helper.util import to_kebab_case

import jsons
import os

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
RESOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'kebab-zrb-app-name')
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, 'deployment')
DEPLOYMENT_TEMPLATE_ENV_FILE_NAME = os.path.join(
    DEPLOYMENT_DIR, 'template.env'
)
APP_DIR = os.path.join(RESOURCE_DIR, 'src')
APP_FRONTEND_DIR = os.path.join(APP_DIR, 'frontend')
APP_FRONTEND_BUILD_DIR = os.path.join(APP_FRONTEND_DIR, 'build')
APP_TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, 'template.env')

LOAD_TEST_DIR = os.path.join(RESOURCE_DIR, 'loadtest')
LOAD_TEST_TEMPLATE_ENV_FILE_NAME = os.path.join(RESOURCE_DIR, 'template.env')

MODULE_CONFIG_PATH = os.path.join(CURRENT_DIR, 'config', 'modules.json')

with open(MODULE_CONFIG_PATH) as file:
    MODULE_JSON_STR = file.read()
MODULES = jsons.loads(MODULE_JSON_STR)

DOCKER_COMPOSE_APP_ENV_FILE_NAME = os.path.join(
    RESOURCE_DIR, 'docker-compose-app.env'
)

SERVICE_CONFIGS: Mapping[str, ServiceConfig] = {}
service_names = [to_kebab_case(module) + '-service' for module in MODULES]
for suffix in ['', 'gateway'] + service_names:
    service_suffix = '-' + suffix if suffix != '' else ''
    service_name = f'kebab-zrb-app-name{service_suffix}'
    SERVICE_CONFIGS[service_name] = ServiceConfig(
        env_files=[
            EnvFile(
                path=APP_TEMPLATE_ENV_FILE_NAME,
                prefix='CONTAINER_ZRB_ENV_PREFIX'
            ),
            EnvFile(
                path=DOCKER_COMPOSE_APP_ENV_FILE_NAME,
                prefix='CONTAINER_ZRB_ENV_PREFIX'
            )
        ],
        envs=[
            Env(
                name='APP_OTEL_EXPORTER_OTLP_ENDPOINT',
                os_name='',
                default='http://otel-collector:4317'
            )
        ]
    )
