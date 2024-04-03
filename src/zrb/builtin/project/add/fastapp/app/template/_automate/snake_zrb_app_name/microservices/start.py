import os

from zrb import Task, python_task, runner
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any

from ..._project import start_project
from .._constant import PREFER_MICROSERVICES
from .._input import host_input, https_input, local_input
from ..container._input import enable_monitoring_input
from ._group import snake_zrb_app_name_microservices_group
from .start_gateway import start_snake_zrb_app_name_gateway
from .start_microservices import start_snake_zrb_app_name_microservices

_CURRENT_DIR = os.path.dirname(__file__)


@python_task(
    icon="🚤",
    name="start",
    description="Start human readable zrb app name as a microservices",
    group=snake_zrb_app_name_microservices_group,
    inputs=[
        local_input,
        enable_monitoring_input,
        host_input,
        https_input,
    ],
    upstreams=[
        start_snake_zrb_app_name_gateway,
        *start_snake_zrb_app_name_microservices,
    ],
)
def start_snake_zrb_app_name_microservices(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Microservices started", color="yellow"))


if PREFER_MICROSERVICES:
    start_snake_zrb_app_name_microservices >> start_project

runner.register(start_snake_zrb_app_name_microservices)
