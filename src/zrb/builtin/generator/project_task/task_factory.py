from typing import Any, Callable, List, Optional
from .._common import project_dir_input, app_name_input
from ....task.decorator import python_task
from ....task.task import Task
from .function import (
    add_project_automation, register_project_start,
    register_project_start_container, register_project_stop_container,
    register_project_remove_container, register_project_build_image,
    register_project_push_image, register_project_deploy,
    register_project_remove_deployment
)
from .task_factory_helper import (
    _get_app_task_file, _get_app_container_task_file,
    _get_app_deployment_task_file, _get_app_start_task_name,
    _get_app_start_container_task_name, _get_app_stop_container_task_name,
    _get_app_remove_container_task_name, _get_app_build_image_task_name,
    _get_app_push_image_task_name, _get_app_deploy_task_name,
    _get_app_remove_deployment_task_name
)


def create_add_project_automation_task(
    upstreams: Optional[List[Task]] = None
) -> Task:
    @python_task(
        name='add-project-automation',
        inputs=[project_dir_input],
        upstreams=[] if upstreams is None else upstreams
    )
    def task(*args: Any, **kwargs: Any):
        project_dir = kwargs.get('project_dir', '.')
        add_project_automation(project_dir)
    return task


def create_register_start_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_task_file
    if get_task_name is None:
        get_task_name = _get_app_start_task_name
    return _create_register_task(
        task_name='register-start',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_start
    )


def create_register_start_container_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_container_task_file
    if get_task_name is None:
        get_task_name = _get_app_start_container_task_name
    return _create_register_task(
        task_name='register-start-container',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_start_container
    )


def create_register_stop_container_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_container_task_file
    if get_task_name is None:
        get_task_name = _get_app_stop_container_task_name
    return _create_register_task(
        task_name='register-stop-container',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_stop_container
    )


def create_register_remove_container_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_container_task_file
    if get_task_name is None:
        get_task_name = _get_app_remove_container_task_name
    return _create_register_task(
        task_name='register-remove-container',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_remove_container
    )


def create_register_push_image_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_container_task_file
    if get_task_name is None:
        get_task_name = _get_app_push_image_task_name
    return _create_register_task(
        task_name='register-push-image',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_push_image
    )


def create_register_build_image_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_container_task_file
    if get_task_name is None:
        get_task_name = _get_app_build_image_task_name
    return _create_register_task(
        task_name='register-build-image',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_build_image
    )


def create_register_deploy_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_deployment_task_file
    if get_task_name is None:
        get_task_name = _get_app_deploy_task_name
    return _create_register_task(
        task_name='register-deploy',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_deploy
    )


def create_remove_deployment_task(
    upstreams: Optional[List[Task]] = None,
    get_file_name: Optional[Callable[..., str]] = None,
    get_task_name: Optional[Callable[..., str]] = None,
):
    if get_file_name is None:
        get_file_name = _get_app_deployment_task_file
    if get_task_name is None:
        get_task_name = _get_app_remove_deployment_task_name
    return _create_register_task(
        task_name='register-remove-deployment',
        upstreams=upstreams,
        get_file_name=get_file_name,
        get_task_name=get_task_name,
        register=register_project_remove_deployment
    )


def _create_register_task(
    task_name: str,
    upstreams: List[Task] = None,
    get_file_name: Callable[..., str] = None,
    get_task_name: Callable[..., str] = None,
    register: Callable[[str, str, str], Any] = None
):
    @python_task(
        name=task_name,
        inputs=[project_dir_input, app_name_input],
        upstreams=[] if upstreams is None else upstreams
    )
    def task(*args: Any, **kwargs: Any):
        project_dir = kwargs.get('project_dir', '.')
        file_name = get_file_name(*args, **kwargs)
        task_name = get_task_name(*args, **kwargs)
        register(project_dir, file_name, task_name)
    return task
