from typing import List
from zrb import CmdTask, Env, HTTPChecker, Task, EnvFile, runner
from zrb.helper.util import to_snake_case, to_kebab_case
from ._common import (
    CURRENT_DIR, APP_DIR, SKIP_LOCAL_MICROSERVICES_EXECUTION,
    APP_TEMPLATE_ENV_FILE_NAME, MODULES, local_app_broker_type_env,
    local_input, mode_input, host_input, https_input
)
import os


def get_start_microservices(upstreams: List[Task]) -> List[Task]:
    start_microservices: List[Task] = []
    for index, module in enumerate(MODULES):
        kebab_module_name = to_kebab_case(module)
        snake_module_name = to_snake_case(module)
        upper_snake_module_name = snake_module_name.upper()
        # Create service_env_file
        service_env_file = EnvFile(
            env_file=APP_TEMPLATE_ENV_FILE_NAME,
            prefix=f'ENV_PREFIX_{upper_snake_module_name}'
        )
        # Create service_envs
        service_port_str = str(httpPort + index + 1)
        service_app_port_env = Env(
            name='APP_PORT',
            os_name=f'ENV_PREFIX_{upper_snake_module_name}_APP_PORT',
            default=service_port_str
        )
        service_envs = [
            local_app_broker_type_env,
            service_app_port_env,
        ]
        # Create service_checker
        service_checker = HTTPChecker(
            name=f'check-kebab-app-name-{kebab_module_name}-service',
            host='{{input.snake_app_name_host}}',
            url='/readiness',
            port='{{env.APP_PORT}}',
            is_https='{{input.snake_app_name_https}}',
            skip_execution=SKIP_LOCAL_MICROSERVICES_EXECUTION
        )
        # Create start_service
        start_service = CmdTask(
            name=f'start-kebab-app-name-{kebab_module_name}-service',
            inputs=[
                local_input,
                mode_input,
                host_input,
                https_input
            ],
            skip_execution=SKIP_LOCAL_MICROSERVICES_EXECUTION,
            upstreams=upstreams,
            cwd=APP_DIR,
            env_files=[service_env_file],
            envs=service_envs,
            cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'start.sh'),
            checkers=[
                service_checker,
            ]
        )
        runner.register(start_service)
        start_microservices.append(start_service)
    return start_microservices
