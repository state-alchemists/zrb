import os
from typing import List

from zrb import CmdTask, Env, EnvFile, HTTPChecker, Task
from zrb.helper.util import to_kebab_case, to_snake_case

from ._config import APP_DIR, APP_TEMPLATE_ENV_FILE_NAME, CURRENT_DIR, MODULES
from ._env import app_enable_otel_env
from ._helper import should_start_local_microservices
from ._input import (
    enable_monitoring_input,
    host_input,
    https_input,
    local_input,
    run_mode_input,
)


def get_start_microservices(upstreams: List[Task]) -> List[Task]:
    disable_all_module_envs = _get_disable_all_module_envs()
    start_microservices: List[Task] = []
    for module_index, module_name in enumerate(MODULES):
        kebab_module_name = to_kebab_case(module_name)
        # Define start service task
        start_service = CmdTask(
            name=f"start-kebab-zrb-app-name-{kebab_module_name}-service",
            inputs=[
                local_input,
                run_mode_input,
                host_input,
                https_input,
                enable_monitoring_input,
            ],
            should_execute=should_start_local_microservices,
            upstreams=upstreams,
            cwd=APP_DIR,
            env_files=[_get_service_env_file(module_name)],
            envs=disable_all_module_envs
            + _get_service_envs(zrbAppHttpPort, module_index, module_name),
            cmd_path=[
                os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
                os.path.join(CURRENT_DIR, "cmd", "app-start.sh"),
            ],
            checkers=[
                HTTPChecker(
                    name=f"check-kebab-zrb-app-name-{kebab_module_name}-service",
                    host="{{input.snake_zrb_app_name_host}}",
                    url="/readiness",
                    port="{{env.APP_PORT}}",
                    is_https="{{input.snake_zrb_app_name_https}}",
                    should_execute=should_start_local_microservices,
                )
            ],
        )
        start_microservices.append(start_service)
    return start_microservices


def _get_service_envs(base_port: int, module_index: int, module_name: str) -> List[Env]:
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


def _get_service_env_file(module_name: str) -> EnvFile:
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    return EnvFile(
        path=APP_TEMPLATE_ENV_FILE_NAME,
        prefix=f"ZRB_ENV_PREFIX_{upper_snake_module_name}",
    )


def _get_disable_all_module_envs() -> List[Env]:
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
