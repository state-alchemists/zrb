import os
from typing import Mapping

import jsons

from zrb import Env, EnvFile, ServiceConfig
from zrb.helper.util import to_kebab_case

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-app-name")
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, "deployment")
DEPLOYMENT_TEMPLATE_ENV_FILE_NAME = os.path.join(DEPLOYMENT_DIR, "template.env")
APP_DIR = os.path.join(RESOURCE_DIR, "src")
APP_FRONTEND_DIR = os.path.join(APP_DIR, "frontend")
APP_FRONTEND_BUILD_DIR = os.path.join(APP_FRONTEND_DIR, "build")
APP_TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, "template.env")
LOAD_TEST_DIR = os.path.join(RESOURCE_DIR, "loadtest")
LOAD_TEST_TEMPLATE_ENV_FILE_NAME = os.path.join(RESOURCE_DIR, "template.env")

MODULE_CONFIG_PATH = os.path.join(CURRENT_DIR, "config", "modules.json")

with open(MODULE_CONFIG_PATH) as file:
    MODULE_JSON_STR = file.read()
MODULES = jsons.loads(MODULE_JSON_STR)

###############################################################################
# Service Configs
###############################################################################

_OTEL_EXPORTER_ENDPOINT_ENV = Env(
    name="APP_OTEL_EXPORTER_OTLP_ENDPOINT",
    os_name="",
    default="http://otel-collector:4317",
)

_CONTAINER_ENV_PREFIX = "CONTAINER_ZRB_ENV_PREFIX"
_APP_TEMPLATE_ENV_FILE = EnvFile(
    path=APP_TEMPLATE_ENV_FILE_NAME, prefix=_CONTAINER_ENV_PREFIX
)
_DOCKER_COMPOSE_APP_ENV_FILE_NAME = os.path.join(RESOURCE_DIR, "docker-compose-app.env")
_DOCKER_COMPOSE_APP_ENV_FILE = EnvFile(
    path=_DOCKER_COMPOSE_APP_ENV_FILE_NAME, prefix=_CONTAINER_ENV_PREFIX
)
_DISABLE_ALL_MODULE_ENV_FILE_NAME = os.path.join(
    RESOURCE_DIR, "all-module-disabled.env"
)
_DISABLE_ALL_MODULE_ENV_FILE = EnvFile(
    path=_DISABLE_ALL_MODULE_ENV_FILE_NAME, prefix=_CONTAINER_ENV_PREFIX
)
_ENABLE_ALL_MODULE_ENV_FILE_NAME = os.path.join(RESOURCE_DIR, "all-module-enabled.env")
_ENABLE_ALL_MODULE_ENV_FILE = EnvFile(
    path=_ENABLE_ALL_MODULE_ENV_FILE_NAME, prefix=_CONTAINER_ENV_PREFIX
)

SERVICE_CONFIGS: Mapping[str, ServiceConfig] = {
    "kebab-zrb-app-name": ServiceConfig(
        env_files=[
            _APP_TEMPLATE_ENV_FILE,
            _DOCKER_COMPOSE_APP_ENV_FILE,
            _ENABLE_ALL_MODULE_ENV_FILE,
        ],
        envs=[_OTEL_EXPORTER_ENDPOINT_ENV],
    ),
    "kebab-zrb-app-name-gateway": ServiceConfig(
        env_files=[
            _APP_TEMPLATE_ENV_FILE,
            _DOCKER_COMPOSE_APP_ENV_FILE,
            _ENABLE_ALL_MODULE_ENV_FILE,
        ],
        envs=[_OTEL_EXPORTER_ENDPOINT_ENV],
    ),
}
for module in MODULES:
    service_name = f"kebab-zrb-app-name-{to_kebab_case(module)}-service"
    SERVICE_CONFIGS[service_name] = ServiceConfig(
        env_files=[
            _APP_TEMPLATE_ENV_FILE,
            _DOCKER_COMPOSE_APP_ENV_FILE,
            _DISABLE_ALL_MODULE_ENV_FILE,
        ],
        envs=[_OTEL_EXPORTER_ENDPOINT_ENV],
    )
