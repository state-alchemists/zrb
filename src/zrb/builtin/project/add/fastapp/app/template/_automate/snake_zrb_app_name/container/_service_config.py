import os
from typing import Mapping

from zrb import Env, EnvFile, ServiceConfig
from zrb.helper.util import to_kebab_case

from .._constant import APP_TEMPLATE_ENV_FILE_NAME, MODULES, RESOURCE_DIR

_otel_exporter_endpoint_env = Env(
    name="APP_OTEL_EXPORTER_OTLP_ENDPOINT",
    os_name="",
    default="http://otel-collector:4317",
)

_container_env_prefix = "CONTAINER_ZRB_ENV_PREFIX"
_app_template_env_file = EnvFile(
    path=APP_TEMPLATE_ENV_FILE_NAME, prefix=_container_env_prefix
)
_docker_compose_app_env_file_name = os.path.join(RESOURCE_DIR, "docker-compose-app.env")
_docker_compose_app_env_file = EnvFile(
    path=_docker_compose_app_env_file_name, prefix=_container_env_prefix
)
_disable_all_module_env_file_name = os.path.join(
    RESOURCE_DIR, "all-module-disabled.env"
)
_disable_all_module_env_file = EnvFile(
    path=_disable_all_module_env_file_name, prefix=_container_env_prefix
)
_enable_all_module_env_file_name = os.path.join(RESOURCE_DIR, "all-module-enabled.env")
_enable_all_module_env_file = EnvFile(
    path=_enable_all_module_env_file_name, prefix=_container_env_prefix
)

snake_zrb_app_name_service_configs: Mapping[str, ServiceConfig] = {
    "kebab-zrb-app-name": ServiceConfig(
        env_files=[
            _app_template_env_file,
            _docker_compose_app_env_file,
            _enable_all_module_env_file,
        ],
        envs=[_otel_exporter_endpoint_env],
    ),
    "kebab-zrb-app-name-gateway": ServiceConfig(
        env_files=[
            _app_template_env_file,
            _docker_compose_app_env_file,
            _enable_all_module_env_file,
        ],
        envs=[_otel_exporter_endpoint_env],
    ),
}
for module in MODULES:
    service_name = f"kebab-zrb-app-name-{to_kebab_case(module)}-service"
    snake_zrb_app_name_service_configs[service_name] = ServiceConfig(
        env_files=[
            _app_template_env_file,
            _docker_compose_app_env_file,
            _disable_all_module_env_file,
        ],
        envs=[_otel_exporter_endpoint_env],
    )
