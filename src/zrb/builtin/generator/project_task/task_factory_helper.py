import os


def _get_app_local_task_file(project_dir: str, snake_app_name: str) -> str:
    return os.path.join(
        project_dir, '_automate', snake_app_name, 'local.py'
    )


def _get_app_container_task_file(project_dir: str, snake_app_name: str) -> str:
    return os.path.join(
        project_dir, '_automate', snake_app_name, 'container.py'
    )


def _get_app_image_task_file(project_dir: str, snake_app_name: str) -> str:
    return os.path.join(
        project_dir, '_automate', snake_app_name, 'image.py'
    )


def _get_app_deployment_task_file(
    project_dir: str, snake_app_name: str
) -> str:
    return os.path.join(
        project_dir, '_automate', snake_app_name, 'deployment.py'
    )


def _get_app_start_task_var(snake_app_name: str) -> str:
    return f'start_{snake_app_name}'


def _get_app_start_container_task_var(snake_app_name: str) -> str:
    return f'start_{snake_app_name}_container'


def _get_app_stop_container_task_var(snake_app_name: str) -> str:
    return f'stop_{snake_app_name}_container'


def _get_app_remove_container_var(snake_app_name: str) -> str:
    return f'remove_{snake_app_name}_container'


def _get_app_push_image_task_var(snake_app_name: str) -> str:
    return f'push_{snake_app_name}_image'


def _get_app_build_image_task_var(snake_app_name: str) -> str:
    return f'build_{snake_app_name}_image'


def _get_app_deploy_task_var(snake_app_name: str) -> str:
    return f'deploy_{snake_app_name}'


def _get_app_destroy_task_var(snake_app_name: str) -> str:
    return f'destroy_{snake_app_name}'
