from typing import Any
from ....helper import util
import os


def _get_app_task_file(*args: Any, **kwargs: Any) -> str:
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}.py'
    )
    return file_name


def _get_app_container_task_file(*args: Any, **kwargs: Any) -> str:
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}_container.py'
    )
    return file_name


def _get_app_deployment_task_file(*args: Any, **kwargs: Any) -> str:
    project_dir = kwargs.get('project_dir', '.')
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    file_name = os.path.join(
        project_dir, '_automate', f'{snake_app_name}_deployment.py'
    )
    return file_name


def _get_app_start_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'start_{snake_app_name}'


def _get_app_start_container_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'start_{snake_app_name}_container'


def _get_app_stop_container_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'stop_{snake_app_name}_container'


def _get_app_remove_container_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'remove_{snake_app_name}_container'


def _get_app_push_image_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'push_{snake_app_name}_image'


def _get_app_build_image_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'build_{snake_app_name}_image'


def _get_app_deploy_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'deploy_{snake_app_name}_image'


def _get_app_remove_deployment_task_name(*args: Any, **kwargs: Any) -> str:
    app_name = kwargs.get('app_name')
    snake_app_name = util.to_snake_case(app_name)
    return f'remove_{snake_app_name}_deployment'
