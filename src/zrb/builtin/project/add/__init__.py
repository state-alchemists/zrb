from zrb.builtin.project.add._group import project_add_group
from zrb.builtin.project.add.plugin import project_add_plugin_group, add_plugin
from zrb.builtin.project.add.project_task import add_project_tasks
from zrb.builtin.project.add.task import (
    project_add_task_group, add_cmd_task, add_docker_compose_task, add_python_task
)

assert project_add_group
assert project_add_plugin_group
assert project_add_task_group
assert add_plugin
assert add_project_tasks
assert add_cmd_task
assert add_docker_compose_task
assert add_python_task
