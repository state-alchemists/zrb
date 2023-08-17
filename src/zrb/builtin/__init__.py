from . import base64
from . import env
from . import eval
from . import git
from . import md5
from . import explain
from . import project
from . import ubuntu
from . import update
from . import version
from .devtool import devtool_install
from .generator.project import create as create_project
from .generator.cmd_task import add as add_cmd_task
from .generator.docker_compose_task import add as add_docker_compose_task
from .generator.python_task import add as add_python_task
from .generator.simple_python_app import add as add_simple_python_app
from .generator.fastapp import add as add_fastapp
from .generator.fastapp_module import add as add_fastapp_module
from .generator.fastapp_crud import add as add_fastapp_crud
from .generator.fastapp_field import add as add_fastapp_field
from .generator.pip_package import add as add_pip_package
from .generator.app_generator import add as add_app_generator

assert base64
assert env
assert eval
assert git
assert md5
assert explain
assert project
assert ubuntu
assert update
assert version
assert devtool_install
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
