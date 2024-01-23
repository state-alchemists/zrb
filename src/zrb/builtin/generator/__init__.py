from zrb.builtin.generator.app_generator import add as add_app_generator
from zrb.builtin.generator.cmd_task.add import add_cmd_task
from zrb.builtin.generator.docker_compose_task.add import add_docker_compose_task
from zrb.builtin.generator.fastapp import add as add_fastapp
from zrb.builtin.generator.fastapp_crud import add as add_fastapp_crud
from zrb.builtin.generator.fastapp_field import add as add_fastapp_field
from zrb.builtin.generator.fastapp_module import add as add_fastapp_module
from zrb.builtin.generator.pip_package import add as add_pip_package
from zrb.builtin.generator.plugin import create as create_plugin
from zrb.builtin.generator.project.create import create_project
from zrb.builtin.generator.python_task.add import add_python_task
from zrb.builtin.generator.simple_python_app import add as add_simple_python_app

assert create_project
assert create_plugin
assert add_cmd_task
assert add_docker_compose_task
assert add_python_task
assert add_simple_python_app
assert add_fastapp
assert add_fastapp_module
assert add_fastapp_crud
assert add_fastapp_field
assert add_pip_package
assert add_app_generator
