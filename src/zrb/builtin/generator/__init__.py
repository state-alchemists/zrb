from . import common
from . import project_task
from .project.create import create_project
from .cmd_task.add import add_cmd_task
from .docker_compose_task.add import add_docker_compose_task
from .python_task.add import add_python_task
from .simple_python_app import add as add_simple_python_app
from .fastapp import add as add_fastapp
from .fastapp_module import add as add_fastapp_module
from .fastapp_crud import add as add_fastapp_crud
from .fastapp_field import add as add_fastapp_field
from .pip_package import add as add_pip_package
from .app_generator import add as add_app_generator

assert common
assert project_task
assert create_project
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
