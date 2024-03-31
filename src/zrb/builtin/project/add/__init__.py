from zrb.builtin.project.add._group import project_add_group
from zrb.builtin.project.add.app import (
    add_app_generator,
    add_python_app,
    project_add_app_group,
)
from zrb.builtin.project.add.fastapp import (
    add_fastapp_application,
    add_fastapp_crud,
    add_fastapp_field,
    add_fastapp_module,
    project_add_fastapp_group,
)
from zrb.builtin.project.add.plugin import add_plugin
from zrb.builtin.project.add.project_task import add_project_tasks
from zrb.builtin.project.add.task import (
    add_cmd_task,
    add_docker_compose_task,
    add_python_task,
    project_add_task_group,
)

assert project_add_group
assert project_add_app_group
assert project_add_fastapp_group
assert project_add_task_group
assert add_app_generator
assert add_python_app
assert add_fastapp_application
assert add_fastapp_crud
assert add_fastapp_field
assert add_fastapp_module
assert add_plugin
assert add_project_tasks
assert add_cmd_task
assert add_docker_compose_task
assert add_python_task
