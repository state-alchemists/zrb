from typing import Any, Callable, List, Optional
from .._common import project_dir_input, app_name_input
from ....task.decorator import python_task
from ....task.task import Task
from ....helper import util
from ....helper.codemod.add_import_module import add_import_module
from ....helper.codemod.add_upstream_to_task import add_upstream_to_task
from .add import add_project_automation
from .task_factory_helper import (
    _get_app_local_task_file, _get_app_container_task_file,
    _get_app_deployment_task_file, _get_app_start_task_var,
    _get_app_start_container_task_var, _get_app_stop_container_task_var,
    _get_app_remove_container_var, _get_app_build_image_task_var,
    _get_app_push_image_task_var, _get_app_deploy_task_var,
    _get_app_remove_deployment_task_var
)
import os


def create_add_project_automation(
    upstreams: Optional[List[Task]] = None
) -> Task:
    @python_task(
        name='add-project-automation',
        inputs=[project_dir_input],
        upstreams=[] if upstreams is None else upstreams
    )
    def _task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir', '.')
        task.print_out('Create project automation modules if not exist')
        add_project_automation(project_dir)
    return _task


def create_register_app_start(
    upstreams: Optional[List[Task]] = None,
):
    return _create_register_app_task(
        task_name='register-start',
        upstreams=upstreams,
        project_automation_file='start_project.py',
        project_automation_task_name='start',
        get_file_name=_get_app_local_task_file,
        get_task_var=_get_app_start_task_var,
    )


def create_register_app_start_container(
    upstreams: Optional[List[Task]] = None,
    as_local_task: bool = False
):
    project_automation_file = 'start_project_containers.py'
    if as_local_task:
        project_automation_file = 'start_project.py'
    project_automation_task_name = 'start-containers'
    if as_local_task:
        project_automation_task_name = 'start'
    return _create_register_app_task(
        task_name='register-start-container',
        upstreams=upstreams,
        project_automation_file=project_automation_file,
        project_automation_task_name=project_automation_task_name,
        get_file_name=_get_app_container_task_file,
        get_task_var=_get_app_start_container_task_var,
    )


def create_register_app_stop_container(
    upstreams: Optional[List[Task]] = None,
):
    return _create_register_app_task(
        task_name='register-stop-container',
        upstreams=upstreams,
        project_automation_file='stop_project_containers.py',
        project_automation_task_name='stop-containers',
        get_file_name=_get_app_container_task_file,
        get_task_var=_get_app_stop_container_task_var,
    )


def create_register_app_remove_container(
    upstreams: Optional[List[Task]] = None,
):
    return _create_register_app_task(
        task_name='register-remove-container',
        upstreams=upstreams,
        project_automation_file='remove_project_containers.py',
        project_automation_task_name='remove-containers',
        get_file_name=_get_app_container_task_file,
        get_task_var=_get_app_remove_container_var,
    )


def create_register_app_push_image(
    upstreams: Optional[List[Task]] = None,
):
    return _create_register_app_task(
        task_name='register-push-image',
        upstreams=upstreams,
        project_automation_file='push_project_images.py',
        project_automation_task_name='push-images',
        get_file_name=_get_app_container_task_file,
        get_task_var=_get_app_push_image_task_var
    )


def create_register_app_build_image(
    upstreams: Optional[List[Task]] = None,
):
    return _create_register_app_task(
        task_name='register-build-image',
        upstreams=upstreams,
        project_automation_file='build_project_images.py',
        project_automation_task_name='build-images',
        get_file_name=_get_app_container_task_file,
        get_task_var=_get_app_build_image_task_var
    )


def create_register_app_deploy(
    upstreams: Optional[List[Task]] = None,
):
    return _create_register_app_task(
        task_name='register-deploy',
        upstreams=upstreams,
        project_automation_file='deploy_project.py',
        project_automation_task_name='deploy',
        get_file_name=_get_app_deployment_task_file,
        get_task_var=_get_app_deploy_task_var
    )


def create_register_app_remove_deployment(
    upstreams: Optional[List[Task]] = None,
):
    return _create_register_app_task(
        task_name='register-remove-deployment',
        project_automation_file='remove_project_deployment.py',
        project_automation_task_name='remove-deployment',
        upstreams=upstreams,
        get_file_name=_get_app_deployment_task_file,
        get_task_var=_get_app_remove_deployment_task_var
    )


def _create_register_app_task(
    task_name: str,
    project_automation_file: str,
    project_automation_task_name: str,
    upstreams: Optional[List[Task]] = None,
    get_file_name: Callable[[str, str], str] = None,
    get_task_var: Callable[[str], str] = None,
):
    @python_task(
        name=task_name,
        inputs=[project_dir_input, app_name_input],
        upstreams=[] if upstreams is None else upstreams
    )
    def _task(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        project_dir = kwargs.get('project_dir', '.')
        app_name = kwargs.get('app_name')
        snake_app_name = util.to_snake_case(app_name)
        upstream_task_file = get_file_name(project_dir, snake_app_name)
        upstream_task_var = get_task_var(snake_app_name)
        project_automation_dir = os.path.join(
            project_dir, '_automate', '_project'
        )
        project_automation_path = os.path.join(
            project_automation_dir, f'{project_automation_file}'
        )
        upstream_task_rel_file_path = os.path.relpath(
            upstream_task_file, project_automation_path
        )
        # normalize `..` parts
        upstream_module_parts = [
            part if part != '..' else ''
            for part in upstream_task_rel_file_path.split(os.path.sep)
        ]
        # remove .py extenstion
        last_part = upstream_module_parts[-1]
        upstream_module_parts[-1] = os.path.splitext(last_part)[0]
        # turn into module path
        upstream_module_path = '.'.join(upstream_module_parts)
        task.print_out(f'Add {upstream_task_var} to project automation')
        with open(project_automation_path, 'r') as f:
            code = f.read()
            code = add_import_module(
                code=code,
                module_path=upstream_module_path,
                resource=upstream_task_var
            )
            code = add_upstream_to_task(
                code, project_automation_task_name, upstream_task_var
            )
        with open(project_automation_path, 'w') as f:
            f.write(code)

    return _task
