import os

from zrb.builtin.generator.common.helper import (
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.generator.common.task_factory import create_register_module
from zrb.builtin.generator.common.task_input import (
    env_prefix_input,
    http_port_input,
    project_dir_input,
    task_name_input,
)
from zrb.builtin.group import project_add_group
from zrb.helper import util
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

CURRENT_DIR = os.path.dirname(__file__)

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="validate",
    inputs=[project_dir_input, task_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    task_name = kwargs.get("task_name")
    validate_inexisting_automation(project_dir, task_name)
    source_dir = os.path.join(project_dir, "src", f"{util.to_kebab_case(task_name)}")
    if os.path.exists(source_dir):
        raise Exception(f"Source already exists: {source_dir}")


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        task_name_input,
        http_port_input,
        StrInput(
            name="compose-command",
            description="Compose command (e.g., up, down, start, remove, etc)",
            prompt="Compose command (e.g., up, down, start, remove, etc)",
            default="up",
        ),
        env_prefix_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbTaskName": "{{input.task_name}}",
        "zrbHttpPort": '{{util.coalesce(input.http_port, "3001")}}',
        "zrbComposeCommand": '{{ util.coalesce(input.compose_command, "up") }}',  # noqa
        "ZRB_ENV_PREFIX": '{{ util.coalesce(input.env_prefix, "MY").upper() }}',  # noqa
    },
    template_path=os.path.join(CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
)

register_module = create_register_module(
    module_path="_automate.{{util.to_snake_case(input.task_name)}}",
    inputs=[task_name_input],
    upstreams=[copy_resource],
)


@python_task(
    name="docker-compose-task",
    group=project_add_group,
    upstreams=[register_module],
    runner=runner,
)
async def add_docker_compose_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out("Success")
