from zrb.builtin.project._group import project_group
from zrb.builtin.project.add import (
    project_add_group,
    project_add_app_group,
    project_add_fastapp_group,
    project_add_task_group,
    add_plugin,
    add_project_tasks,
    add_cmd_task,
    add_docker_compose_task,
    add_fastapp_application,
    add_fastapp_crud,
    add_fastapp_field,
    add_fastapp_module,
    add_python_task,
    add_python_app
)
from zrb.builtin.project.create import create_project
from zrb.builtin.project.env import project_env_group, get_project_default_env

assert project_group
assert project_add_group
assert project_add_app_group
assert project_add_fastapp_group
assert project_add_task_group
assert project_env_group
assert create_project
assert get_project_default_env
assert add_plugin
assert add_project_tasks
assert add_cmd_task
assert add_docker_compose_task
assert add_fastapp_application
assert add_fastapp_crud
assert add_fastapp_module
assert add_fastapp_field
assert add_python_task
assert add_python_app
