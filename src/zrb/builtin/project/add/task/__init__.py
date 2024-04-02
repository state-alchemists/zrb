from zrb.builtin.project.add.task._group import project_add_task_group
from zrb.builtin.project.add.task.cmd import add_cmd_task
from zrb.builtin.project.add.task.docker_compose import add_docker_compose_task
from zrb.builtin.project.add.task.python import add_python_task

assert project_add_task_group
assert add_cmd_task
assert add_docker_compose_task
assert add_python_task
