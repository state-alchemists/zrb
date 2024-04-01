from typing import List

from zrb import Env, EnvFile
from zrb.helper.util import to_kebab_case, to_snake_case

from .._constant import APP_TEMPLATE_ENV_FILE_NAME, MODULES
from .._env import app_enable_otel_env


def get_service_envs(base_port: int, module_index: int, module_name: str) -> List[Env]:
    kebab_module_name = to_kebab_case(module_name)
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    # Define service env
    app_broker_type_env = Env(
        name="APP_BROKER_TYPE",
        os_name=f"ZRB_ENV_PREFIX_{upper_snake_module_name}_APP_BROKER_TYPE",
        default="rabbitmq",
    )
    app_port_env = Env(
        name="APP_PORT",
        os_name=f"ZRB_ENV_PREFIX_{upper_snake_module_name}_APP_PORT",
        default=str(base_port + module_index + 1),
    )
    enable_module_env = Env(
        name=f"APP_ENABLE_{upper_snake_module_name}_MODULE", os_name="", default="true"
    )
    zrb_app_name_env = Env(
        name="APP_NAME",
        os_name=f"ZRB_ENV_PREFIX_{upper_snake_module_name}_APP_NAME",
        default=f"kebab-zrb-app-name-{kebab_module_name}-service",
    )
    return [
        app_broker_type_env,
        app_enable_otel_env,
        app_port_env,
        zrb_app_name_env,
        enable_module_env,
    ]


def get_service_env_file(module_name: str) -> EnvFile:
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    return EnvFile(
        path=APP_TEMPLATE_ENV_FILE_NAME,
        prefix=f"ZRB_ENV_PREFIX_{upper_snake_module_name}",
    )


def get_disable_all_module_envs() -> List[Env]:
    disable_all_module_envs: List[Env] = []
    for module in MODULES:
        snake_module_name = to_snake_case(module)
        upper_snake_module_name = snake_module_name.upper()
        disable_all_module_envs.append(
            Env(
                name=f"APP_ENABLE_{upper_snake_module_name}_MODULE",
                os_name="",
                default="false",
            )
        )
    return disable_all_module_envs
