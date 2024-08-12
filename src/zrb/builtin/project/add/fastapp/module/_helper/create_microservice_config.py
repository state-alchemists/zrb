import asyncio
import os
from collections.abc import Mapping
from typing import Any

import jsons
from dotenv import dotenv_values

from zrb.helper.docker_compose.file import add_services
from zrb.helper.file.text import (
    append_text_file_async,
    read_text_file_async,
    write_text_file_async,
)
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_kebab_case, to_snake_case
from zrb.task.task import Task


@typechecked
async def create_microservice_config(
    task: Task, project_dir: str, app_name: str, module_name: str
):
    modules = await _create_automation_json_config(
        task, project_dir, app_name, module_name
    )
    return await asyncio.gather(
        asyncio.create_task(
            _add_docker_compose_service(
                task, modules, project_dir, app_name, module_name
            )
        ),
        asyncio.create_task(
            _append_compose_env(task, modules, project_dir, app_name, module_name)
        ),
    )


@typechecked
async def _add_docker_compose_service(
    task: Task, modules: list[str], project_dir: str, app_name: str, module_name: str
):
    kebab_app_name = to_kebab_case(app_name)
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    module_app_port = 8080 + len(modules)
    module_app_port_str = str(module_app_port)
    docker_compose_file_path = os.path.join(
        project_dir, "src", kebab_app_name, "docker-compose.yml"
    )
    app_container_port_env_name = f"APP_{upper_snake_module_name}_MODULE_PORT"
    app_container_port_env = (
        "${" + app_container_port_env_name + ":-" + module_app_port_str + "}"
    )
    app_host_port_env_name = f"APP_{upper_snake_module_name}_HOST_MODULE_PORT"
    app_host_port_env = "${" + app_host_port_env_name + ":-" + module_app_port_str + "}"
    service_definition = _get_new_docker_compose_service_definition(
        app_name=app_name,
        module_name=module_name,
        app_host_port_env=app_host_port_env,
        app_container_port_env=app_container_port_env,
    )
    task.print_out(f"Add service at: {docker_compose_file_path}")
    add_services(
        file_name=docker_compose_file_path,
        new_services=service_definition,
    )


@typechecked
def _get_new_docker_compose_service_definition(
    app_name: str, module_name: str, app_host_port_env: str, app_container_port_env: str
) -> Mapping[str, Any]:
    kebab_app_name = to_kebab_case(app_name)
    kebab_module_name = to_kebab_case(module_name)
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    return {
        f"{kebab_app_name}-{kebab_module_name}-service": {
            "build": {"dockerfile": "Dockerfile", "context": "./src"},
            "image": "${IMAGE:-" + kebab_app_name + "}",
            "container_name": "${CONTAINER_PREFIX:-my}-"
            + f"{kebab_app_name}-{kebab_module_name}-service",  # noqa
            "hostname": f"{kebab_app_name}-{kebab_module_name}-service",
            "env_file": ["src/template.env", "all-module-disabled.env"],
            "environment": {
                "APP_NAME": "${APP_NAME:-"
                + kebab_app_name
                + "}-"
                + f"{kebab_module_name}-service",  # noqa
                "APP_ENABLE_OTEL": "${APP_ENABLE_OTEL:-0}",
                "APP_PORT": app_container_port_env,
                "APP_ENABLE_EVENT_HANDLER": "true",
                "APP_ENABLE_RPC_SERVER": "true",
                "APP_ENABLE_API": "false",
                "APP_ENABLE_FRONTEND": "false",
                f"APP_ENABLE_{upper_snake_module_name}_MODULE": "true",
            },
            "ports": [f"{app_host_port_env}:{app_container_port_env}"],
            "restart": "unless-stopped",
            "profiles": ["microservices"],
            "healthcheck": {
                "test": f"curl --fail http://localhost:{app_container_port_env}/readiness || killall uvicorn",  # noqa
                "interval": "20s",
                "timeout": "3s",
                "retries": 10,
                "start_period": "20s",
            },
            "networks": ["zrb"],
        }
    }


@typechecked
async def _create_automation_json_config(
    task: Task,
    project_dir: str,
    app_name: str,
    module_name: str,
):
    snake_app_name = to_snake_case(app_name)
    snake_module_name = to_snake_case(module_name)
    json_modules_file_path = os.path.join(
        project_dir, "_automate", snake_app_name, "config", "modules.json"
    )
    task.print_out(f"Read json config from: {json_modules_file_path}")
    json_str = await read_text_file_async(json_modules_file_path)
    task.print_out(f'Add "{snake_module_name}" to json config')
    modules: list[str] = jsons.loads(json_str)
    modules.append(snake_module_name)
    json_str = jsons.dumps(modules)
    task.print_out(f"Write new json config to: {json_modules_file_path}")
    await write_text_file_async(json_modules_file_path, json_str)
    return modules


@typechecked
async def _append_compose_env(
    task: Task, modules: list[str], project_dir: str, app_name: str, module_name: str
):
    kebab_app_name = to_kebab_case(app_name)
    snake_module_name = to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    compose_template_env_path = os.path.join(
        project_dir, "src", kebab_app_name, "docker-compose.env"
    )
    compose_env_map = dotenv_values(compose_template_env_path)
    host_port = int(compose_env_map.get("APP_GATEWAY_HOST_PORT", "8080"))
    module_app_port = host_port + len(modules)
    new_env_str = "\n".join(
        [
            f"APP_{upper_snake_module_name}_HOST_MODULE_PORT={module_app_port}",
            f"APP_{upper_snake_module_name}_MODULE_PORT={module_app_port}",
        ]
    )
    task.print_out(f"Add new environment to: {compose_template_env_path}")
    await append_text_file_async(compose_template_env_path, new_env_str)
