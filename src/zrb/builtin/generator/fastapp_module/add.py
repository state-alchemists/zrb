from typing import Any, List, Mapping
from dotenv import dotenv_values
from ..._group import project_add_group
from ....task.task import Task
from ....task.decorator import python_task
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from .._common.input import (
    project_dir_input, app_name_input,
    module_name_input
)
from .._common.helper import validate_project_dir
from .._common.lock import new_task_app_lock
from ....helper import util
from ....helper.codemod.add_import_module import add_import_module
from ....helper.codemod.add_function_call import add_function_call
from ....helper.codemod.append_code_to_function import append_code_to_function
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
    retry=0,
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
    app_dir = os.path.join(
        project_dir, 'src', f'{util.to_kebab_case(app_name)}'
    )
    if not os.path.exists(app_dir):
        raise Exception(f'App directory does not exist: {app_dir}')
    module_path = os.path.join(app_dir, 'src', 'module', snake_module_name)
    if os.path.exists(module_path):
        raise Exception(f'Module directory already exists: {module_path}')


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
    ],
    upstreams=[validate],
    replacements={
        'appName': '{{input.app_name}}',
        'moduleName': '{{input.module_name}}',
    },
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{ input.project_dir }}',
    locks=[new_task_app_lock],
    excludes=[]
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
    await asyncio.gather(
        asyncio.create_task(_create_microservice_config(
            task, project_dir, kebab_app_name, snake_app_name,
            kebab_module_name, snake_module_name, upper_snake_module_name
        )),
        asyncio.create_task(_register_module(
            task, project_dir, kebab_app_name, snake_module_name
        )),
        asyncio.create_task(_register_migration(
            task, project_dir, kebab_app_name, snake_module_name
        )),
        asyncio.create_task(_create_app_config(
            task, project_dir, kebab_app_name, snake_module_name,
            upper_snake_module_name
        )),
        asyncio.create_task(_append_all_enabled_env(
            task, project_dir, kebab_app_name, upper_snake_module_name
        )),
        asyncio.create_task(_append_all_disabled_env(
            task, project_dir, kebab_app_name, upper_snake_module_name
        )),
        asyncio.create_task(_append_src_template_env(
            task, project_dir, kebab_app_name, upper_snake_module_name
        )),
        asyncio.create_task(_append_deployment_template_env(
            task, project_dir, kebab_app_name, upper_snake_module_name
        )),
    )
    task.print_out('Success')


async def _create_microservice_config(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_app_name: str,
    kebab_module_name: str,
    snake_module_name: str,
    upper_snake_module_name: str
):
    modules = await _create_automation_json_config(
        task, project_dir, snake_app_name, snake_module_name
    )
    return await asyncio.gather(
        asyncio.create_task(_add_docker_compose_service(
            task, modules, project_dir, kebab_app_name,
            snake_app_name, kebab_module_name, snake_module_name,
            upper_snake_module_name
        )),
        asyncio.create_task(_append_compose_env(
            task, modules, project_dir, snake_app_name, upper_snake_module_name
        ))
    )


async def _add_docker_compose_service(
    task: Task,
    modules: List[str],
    project_dir: str,
    kebab_app_name: str,
    snake_app_name: str,
    kebab_module_name: str,
    snake_module_name: str,
    upper_snake_module_name: str
):
    module_app_port = 8080 + len(modules)
    module_app_port_str = str(module_app_port)
    docker_compose_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'docker-compose.yml'
    )
    app_container_port_env_name = f'APP_{upper_snake_module_name}_MODULE_PORT'
    app_container_port_env = '${' + app_container_port_env_name + ':-' + module_app_port_str + '}' # noqa
    app_host_port_env_name = f'APP_{upper_snake_module_name}_HOST_MODULE_PORT'
    app_host_port_env = '${' + app_host_port_env_name + ':-' + module_app_port_str + '}' # noqa
    service_definition = _get_new_docker_compose_service_definition(
        kebab_app_name, snake_app_name, kebab_module_name, snake_module_name,
        upper_snake_module_name, app_host_port_env, app_container_port_env
    )
    task.print_out(f'Add service at: {docker_compose_file_path}')
    add_services(
        file_name=docker_compose_file_path,
        new_services=service_definition,
    )


def _get_new_docker_compose_service_definition(
    kebab_app_name: str,
    snake_app_name: str,
    kebab_module_name: str,
    snake_module_name: str,
    upper_snake_module_name: str,
    app_host_port_env: str,
    app_container_port_env: str
) -> Mapping[str, Any]:
    return {
        f'{kebab_app_name}-{kebab_module_name}-service': {
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
                'APP_NAME': '${APP_NAME:-' + kebab_app_name + '}-' + f'{kebab_module_name}-service', # noqa
                'APP_PORT': app_container_port_env,  # noqa
                'APP_RMQ_CONNECTION': '${APP_CONTAINER_RMQ_CONNECTION:-amqp://guest:guest@rabbitmq/}', # noqa
                'APP_KAFKA_BOOTSTRAP_SERVERS': '${APP_CONTAINER_KAFKA_BOOTSTRAP_SERVERS:-redpanda:9092}', # noqa
                'APP_DB_CONNECTION': '${APP_CONTAINER_DB_CONNECTION:-postgresql+psycopg2://postgres:admin@postgresql:5432/' + snake_app_name + '}', # noqa
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
                    "curl --fail http://localhost:${APP_PORT:-8080}/readiness || exit 1" # noqa
                ],
                'interval': '5s',
                'timeout': '3s',
                'retries': 10
            }
        }
    }


async def _append_compose_env(
    task: Task,
    modules: List[str],
    project_dir: str,
    snake_app_name: str,
    upper_snake_module_name: str
):
    compose_template_env_path = os.path.join(
        project_dir, '_automate', snake_app_name, 'config',
        'docker-compose.env'
    )
    compose_env_map = dotenv_values(compose_template_env_path)
    host_port = int(compose_env_map.get('APP_GATEWAY_HOST_PORT', '8080'))
    module_app_port = host_port + len(modules)
    new_env_str = '\n'.join([
        f'APP_{upper_snake_module_name}_HOST_MODULE_PORT={module_app_port}',
        f'APP_{upper_snake_module_name}_MODULE_PORT={module_app_port}',
    ])
    task.print_out(f'Add new environment to: {compose_template_env_path}')
    await append_text_file_async(compose_template_env_path, new_env_str)


async def _append_src_template_env(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    upper_snake_module_name: str
):
    src_template_env_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'template.env'
    )
    new_env_str = '\n'.join([
        f'APP_ENABLE_{upper_snake_module_name}_MODULE=true',
    ])
    task.print_out(f'Add new environment to: {src_template_env_path}')
    await append_text_file_async(src_template_env_path, new_env_str)


async def _append_deployment_template_env(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    upper_snake_module_name: str
):
    deployment_template_env_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'deployment', 'template.env'
    )
    new_env_str = '\n'.join([
        f'REPLICA_{upper_snake_module_name}_SERVICE=1',
    ])
    task.print_out(f'Add new environment to: {deployment_template_env_path}')
    await append_text_file_async(deployment_template_env_path, new_env_str)


async def _append_all_enabled_env(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    upper_snake_module_name: str
):
    all_enabled_env_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'all-module-enabled.env'
    )
    task.print_out(f'Add new environment to: {all_enabled_env_path}')
    await append_text_file_async(
        all_enabled_env_path,
        f'APP_ENABLE_{upper_snake_module_name}_MODULE=true'
    )


async def _append_all_disabled_env(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    upper_snake_module_name: str
):
    all_disabled_env_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'all-module-disabled.env'
    )
    task.print_out(f'Add new environment to: {all_disabled_env_path}')
    await append_text_file_async(
        all_disabled_env_path,
        f'APP_ENABLE_{upper_snake_module_name}_MODULE=false'
    )


async def _create_app_config(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str,
    upper_snake_module_name: str
):
    config_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'config.py'
    )
    config_code = '\n'.join([
        f'app_enable_{snake_module_name}_module = str_to_boolean(os.environ.get(',  # noqa
        f"    'APP_ENABLE_{upper_snake_module_name}_MODULE', 'true'"
        '))'
    ])
    task.print_out(f'Read config from: {config_file_path}')
    code = await read_text_file_async(config_file_path)
    code += '\n' + config_code
    task.print_out(f'Write config to: {config_file_path}')
    await write_text_file_async(config_file_path, code)


async def _create_automation_json_config(
    task: Task,
    project_dir: str,
    snake_app_name: str,
    snake_module_name: str,
):
    json_modules_file_path = os.path.join(
        project_dir, '_automate', snake_app_name, 'config', 'modules.json'
    )
    task.print_out(f'Read json config from: {json_modules_file_path}')
    json_str = await read_text_file_async(json_modules_file_path)
    task.print_out(f'Add "{snake_module_name}" to json config')
    modules: List[str] = jsons.loads(json_str)
    modules.append(snake_module_name)
    json_str = jsons.dumps(modules)
    task.print_out(f'Write new json config to: {json_modules_file_path}')
    await write_text_file_async(json_modules_file_path, json_str)
    return modules


async def _register_migration(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str
):
    app_migration_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'migrate.py'
    )
    import_module_path = '.'.join([
        'module', snake_module_name, 'migrate'
    ])
    function_name = f'migrate_{snake_module_name}'
    task.print_out(f'Read code from: {app_migration_file_path}')
    code = await read_text_file_async(app_migration_file_path)
    task.print_out(
        f'Add import "{function_name}" from "{import_module_path}" to the code'
    )
    code = add_import_module(
        code=code,
        module_path=import_module_path,
        resource=function_name
    )
    task.print_out(f'Add "{function_name}" call to the code')
    code = append_code_to_function(
        code=code,
        function_name='migrate',
        new_code=f'await {function_name}()'
    )
    task.print_out(f'Write modified code to: {app_migration_file_path}')
    await write_text_file_async(app_migration_file_path, code)


async def _register_module(
    task: Task,
    project_dir: str,
    kebab_app_name: str,
    snake_module_name: str
):
    app_main_file_path = os.path.join(
        project_dir, 'src', kebab_app_name, 'src', 'main.py'
    )
    import_module_path = '.'.join([
        'module', snake_module_name, 'register_module'
    ])
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
