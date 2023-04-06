from typing import Any, List
from dotenv import dotenv_values
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common import (
    default_module_inputs, project_dir_input, app_name_input,
    module_name_input, validate_project_dir, get_default_module_replacements,
    get_default_module_replacement_middlewares, new_app_scaffold_lock
)
from ....helper import util
from ....helper.codemod.add_import_module import add_import_module
from ....helper.codemod.add_function_call import add_function_call
from ....helper.docker_compose.file import add_services
from ....helper.file.text import (
    read_text_file_async, write_text_file_async, append_text_file_async
)

import asyncio
import os
import jsons

current_dir = os.path.dirname(__file__)


@python_task(
    name='validate',
    inputs=[project_dir_input, app_name_input, module_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_project_dir(project_dir)
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    snake_module_name = util.to_snake_case(module_name)
    automation_dir = os.path.join(
        project_dir, '_automate', util.to_snake_case(app_name)
    )
    if not os.path.exists(automation_dir):
        raise Exception(
            f'Automation directory does not exist: {automation_dir}'
        )
    source_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if not os.path.exists(source_dir):
        raise Exception(f'Source does not exist: {source_dir}')
    module_path = os.path.join(source_dir, 'module', snake_module_name)
    if os.path.exists(module_path):
        raise Exception(f'Module directory already exists: {module_path}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=default_module_inputs,
    upstreams=[validate],
    replacements=get_default_module_replacements(),
    replacement_middlewares=get_default_module_replacement_middlewares(),
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    scaffold_locks=[new_app_scaffold_lock],
    excludes=[
        '*/deployment/venv',
        '*/src/kebab-app-name/venv',
        '*/src/kebab-app-name/frontend/node_modules',
        '*/src/kebab-app-name/frontend/build',
    ]
)


@python_task(
    name='fastapp-module',
    group=project_add_group,
    upstreams=[copy_resource],
    runner=runner
)
async def add_fastapp_module(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    module_name = kwargs.get('module_name')
    kebab_app_name = util.to_kebab_case(app_name)
    snake_app_name = util.to_snake_case(app_name)
    kebab_module_name = util.to_kebab_case(module_name)
    snake_module_name = util.to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    app_main_file = get_app_main_file(project_dir, kebab_app_name)
    app_config_file = get_app_config_file(project_dir, kebab_app_name)
    json_modules_file = get_json_modules_file(project_dir, snake_app_name)
    enabled_env_file = get_all_enabled_env_file(project_dir, kebab_app_name)
    disabled_env_file = get_all_disabled_env_file(project_dir, kebab_app_name)
    docker_compose_file = get_docker_compose_file(project_dir, kebab_app_name)
    results = await asyncio.gather(*[
        asyncio.create_task(create_automation_json_config(
            task, json_modules_file, snake_module_name
        )),
        asyncio.create_task(register_module(
            task, app_main_file, snake_module_name
        )),
        asyncio.create_task(create_app_config(
            task, app_config_file, snake_module_name, upper_snake_module_name
        )),
        asyncio.create_task(append_all_enabled_env(
            task, enabled_env_file, upper_snake_module_name
        )),
        asyncio.create_task(append_all_disabled_env(
            task, disabled_env_file, upper_snake_module_name
        )),
    ])
    modules = results[0]  # return value of `create_automation_json_config`
    module_port = 8080 + len(modules)
    src_template_env_path = get_src_template_env_file(
        project_dir, kebab_app_name
    )
    src_template_env_map = dotenv_values(src_template_env_path)
    app_port = int(src_template_env_map.get('APP_PORT', '8080'))
    module_app_port = app_port + len(modules)
    compose_env_path = get_compose_env_file(
        project_dir, snake_app_name
    )
    compose_env_map = dotenv_values(compose_env_path)
    host_port = int(compose_env_map.get('APP_GATEWAY_HOST_PORT', '8080'))
    module_host_port = host_port + len(modules)
    await asyncio.gather(*[
        asyncio.create_task(add_docker_compose_service(
            task, module_port, docker_compose_file, kebab_app_name,
            snake_app_name, kebab_module_name, snake_module_name,
            upper_snake_module_name
        )),
        asyncio.create_task(append_src_template_env(
            task, module_app_port, src_template_env_path,
            upper_snake_module_name
        )),
        asyncio.create_task(append_compose_env(
            task, module_host_port, compose_env_path,
            upper_snake_module_name
        ))
    ])
    # TODO: create runner for local microservices
    # TODO: create deployment for local microservices
    task.print_out('Success')


async def add_docker_compose_service(
    task: Task,
    module_app_port: int,
    docker_compose_file_path: str,
    kebab_app_name: str,
    snake_app_name: str,
    kebab_module_name: str,
    snake_module_name: str,
    upper_snake_module_name: str
):
    module_app_port_str = str(module_app_port)
    app_container_port_env_name = f'APP_{upper_snake_module_name}_MODULE_PORT'
    app_container_port_env = '${' + app_container_port_env_name + ':-' + module_app_port_str + '}' # noqa
    app_host_port_env_name = f'APP_{upper_snake_module_name}_HOST_MODULE_PORT'
    app_host_port_env = '${' + app_host_port_env_name + ':-' + module_app_port_str + '}' # noqa
    task.print_out(f'Add service at: {docker_compose_file_path}')
    add_services(
        file_name=docker_compose_file_path,
        new_services={
            f'{kebab_app_name}-{kebab_module_name}-module': {
                'build': {
                    'dockerfile': 'Dockerfile',
                    'context': './src'
                },
                'image': '${IMAGE:-' + kebab_app_name + '}',
                'container_name': f'{snake_app_name}_{snake_module_name}',
                'hostname': f'snake_app_name_{snake_module_name}',
                'env_file': [
                    'src/template.env',
                    'all-module-disabled.env'
                ],
                'environment': {
                    'APP_NAME': '${APP_NAME:-' + kebab_app_name + '}-' + f'{kebab_module_name}-module', # noqa
                    'APP_PORT': app_container_port_env,  # noqa
                    'APP_RMQ_CONNECTION': '${APP_CONTAINER_RMQ_CONNECTION:-amqp://guest:guest@rabbitmq/}', # noqa
                    'APP_KAFKA_BOOTSTRAP_SERVERS': '${APP_CONTAINER_KAFKA_BOOTSTRAP_SERVERS:-redpanda:9092}', # noqa
                    'APP_ENABLE_MESSAGE_CONSUMER': 'true',
                    'APP_ENABLE_RPC_SERVER': 'true',
                    'APP_ENABLE_API': 'false',
                    'APP_ENABLE_FRONTEND': 'false',
                    f'APP_ENABLE_{upper_snake_module_name}_MODULE': 'true',
                },
                'ports': [
                    f'{app_host_port_env}:{app_container_port_env}'
                ],
                'restart': 'on-failure',
                'profiles': [
                    'microservices'
                ],
                'healthcheck': {
                    'test': [
                        "CMD-SHELL",
                        "curl --fail http://localhost:${APP_PORT:-8080}/ || exit 1" # noqa
                    ],
                    'interval': '5s',
                    'timeout': '1s',
                    'retries': 30
                }
            }
        }
    )


async def append_compose_env(
    task: Task,
    module_app_port: int,
    compose_template_env_path: str,
    upper_snake_module_name: str
):
    new_env_str = '\n'.join([
        f'APP_{upper_snake_module_name}_HOST_MODULE_PORT={module_app_port}',
        f'APP_{upper_snake_module_name}_MODULE_PORT={module_app_port}',
    ])
    task.print_out(f'Add new environment to: {compose_template_env_path}')
    await append_text_file_async(compose_template_env_path, new_env_str)


async def append_src_template_env(
    task: Task,
    module_app_port: int,
    src_template_env_path: str,
    upper_snake_module_name: str
):
    new_env_str = '\n'.join([
        f'APP_ENABLE_{upper_snake_module_name}_MODULE=true',
    ])
    task.print_out(f'Add new environment to: {src_template_env_path}')
    await append_text_file_async(src_template_env_path, new_env_str)


async def append_all_enabled_env(
    task: Task,
    all_enabled_env_path: str,
    upper_snake_module_name: str
):
    task.print_out(f'Add new environment to: {all_enabled_env_path}')
    await append_text_file_async(
        all_enabled_env_path,
        f'APP_ENABLE_{upper_snake_module_name}_MODULE=true'
    )


async def append_all_disabled_env(
    task: Task,
    all_disabled_env_path: str,
    upper_snake_module_name: str
):
    task.print_out(f'Add new environment to: {all_disabled_env_path}')
    await append_text_file_async(
        all_disabled_env_path,
        f'APP_ENABLE_{upper_snake_module_name}_MODULE=false'
    )


async def create_app_config(
    task: Task,
    config_file_path: str,
    snake_module_name: str,
    upper_snake_module_name: str
):
    config_code = '\n'.join([
        f'app_enable_{snake_module_name}_module = str_to_boolean(os.environ.get(',  # noqa
        f"    'APP_{upper_snake_module_name}', 'true'"
        '))'
    ])
    task.print_out(f'Read config from: {config_file_path}')
    code = await read_text_file_async(config_file_path)
    code += '\n' + config_code
    task.print_out(f'Write config to: {config_file_path}')
    await write_text_file_async(config_file_path, code)


async def create_automation_json_config(
    task: Task,
    json_modules_file_path: str,
    snake_module_name: str,
):
    task.print_out(f'Read json config from: {json_modules_file_path}')
    json_str = await read_text_file_async(json_modules_file_path)
    task.print_out(f'Add "{snake_module_name}" to json config')
    modules: List[str] = jsons.loads(json_str)
    modules.append(snake_module_name)
    json_str = jsons.dumps(modules)
    task.print_out(f'Write new json config to: {json_modules_file_path}')
    await write_text_file_async(json_modules_file_path, json_str)
    return modules


async def register_module(
    task: Task,
    app_main_file_path: str,
    snake_module_name: str
):
    import_module_path = '.'.join(['module', snake_module_name])
    function_name = f'register_{snake_module_name}'
    task.print_out(f'Read code from: {app_main_file_path}')
    code = await read_text_file_async(app_main_file_path)
    task.print_out(
        f'Add import "{function_name}" from "{import_module_path}" to the code'
    )
    code = add_import_module(
        code=code,
        module_path=import_module_path,
        resource=function_name
    )
    task.print_out(f'Add "{function_name}" call to the code')
    code = add_function_call(
        code=code,
        function_name=function_name,
        parameters=[]
    )
    task.print_out(f'Write modified code to: {app_main_file_path}')
    await write_text_file_async(app_main_file_path, code)


def get_docker_compose_file(project_dir: str, kebab_app_name: str):
    return os.path.join(
        project_dir, 'src', kebab_app_name, 'docker-compose.yml'
    )


def get_app_main_file(project_dir: str, kebab_app_name: str):
    return os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'main.py'
    )


def get_app_config_file(project_dir: str, kebab_app_name: str):
    return os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'config.py'
    )


def get_json_modules_file(project_dir: str, snake_app_name: str):
    return os.path.join(
        project_dir, '_automate', snake_app_name, 'config', 'modules.json'
    )


def get_compose_env_file(project_dir: str, snake_app_name: str):
    return os.path.join(
        project_dir, '_automate', snake_app_name, 'config',
        'docker-compose.env'
    )


def get_src_template_env_file(project_dir: str, kebab_app_name: str):
    return os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'template.env'
    )


def get_all_enabled_env_file(project_dir: str, kebab_app_name: str):
    return os.path.join(
        project_dir, 'src', kebab_app_name, 'all-module-enabled.env'
    )


def get_all_disabled_env_file(project_dir: str, kebab_app_name: str):
    return os.path.join(
        project_dir, 'src', kebab_app_name, 'all-module-disabled.env'
    )

