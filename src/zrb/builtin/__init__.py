from . import base64
from . import env
from . import eval
from . import md5
from . import principle
from . import project
from . import ubuntu
from . import update
from . import version
from .devtool import devtool_install
from .generator.project import create as generate_project
from .generator.cmd_task import add as generate_cmd_task
from .generator.docker_compose_task import add as generate_docker_compose_task
from .generator.python_task import add as generate_python_task
from .generator.simple_python_app import add as generate_simple_python_app
from .generator.fastapp import add as generate_fastapp
from .generator.fastapp_module import add as generate_fastapp_module
from .generator.fastapp_crud import add as generate_fastapp_crud
from .generator.fastapp_field import add as generate_fastapp_field

assert base64
assert env
assert eval
assert md5
assert principle
assert project
assert ubuntu
assert update
assert version
assert devtool_install
assert generate_project
assert generate_cmd_task
assert generate_docker_compose_task
assert generate_python_task
assert generate_simple_python_app
assert generate_fastapp
assert generate_fastapp_module
assert generate_fastapp_crud
assert generate_fastapp_field
