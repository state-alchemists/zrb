import os

from zrb.builtin.generator.common.helper import (
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.generator.common.task_factory import create_register_module
from zrb.builtin.generator.common.task_input import project_dir_input
from zrb.builtin.group import project_add_group
from zrb.helper.accessories.name import get_random_name
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task
from zrb.task_input.bool_input import BoolInput
from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput

CURRENT_DIR = os.path.dirname(__file__)

###############################################################################
# Task Input Definitions
###############################################################################

template_name_input = StrInput(
    name="template-name",
    shortcut="t",
    description="Template name",
    prompt="Template name",
    default=get_random_name(),
)

base_image_input = StrInput(
    name="base-image",
    shortcut="i",
    description="Base image",
    prompt="Base image",
    default="stalchmst/moku:1.0.0",
)

default_app_port_input = IntInput(
    name="default-app-port",
    shortcut="p",
    description="Default app port",
    prompt="Default app port",
    default="8080",
)

build_custom_image_input = BoolInput(
    name="build-custom-image",
    description="Whether build custom image or not",
    prompt="Does user need to create custom image?",
    default=True,
)

is_container_only_input = BoolInput(
    name="is-container-only",
    description="Whether app only run as container or not",
    prompt="Is this container only?",
    default=False,
)

is_http_port_input = BoolInput(
    name="is-http-port",
    description="Whether app run on top of HTTP(s) protocol or not",
    prompt="Is this a web appp (run on top of HTTP(s))?",
    default=False,
)

use_helm_input = BoolInput(
    name="use-helm",
    description="Whether using helm for deployment or not",
    prompt="Do you want to use helm for deployment?",
    default=False,
)

###############################################################################
# Task Properties
###############################################################################

inputs = [
    project_dir_input,
    template_name_input,
    default_app_port_input,
    is_http_port_input,
    base_image_input,
    build_custom_image_input,
    is_container_only_input,
    use_helm_input,
]

replacements = {
    "zrbMetaTemplateName": "{{input.template_name}}",
    "zrbMetaBaseImage": "{{input.base_image}}",
    "zrbMetaDefaultAppPort": "{{input.default_app_port}}",
}

###############################################################################
# Task Definitions
###############################################################################


@python_task(name="validate", inputs=inputs, retry=0)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    template_name = kwargs.get("template_name")
    validate_inexisting_automation(project_dir, template_name)
    is_container_only_input: bool = kwargs.get("is_container_only")
    build_custom_image_input: bool = kwargs.get("build_custom_image")
    if not is_container_only_input and not build_custom_image_input:
        raise Exception(
            "Invalid options: Not is-container-only but not build-custom-image"
        )


copy_base_resource = ResourceMaker(
    name="copy-base-resource",
    inputs=inputs,
    upstreams=[validate],
    replacements=replacements,
    template_path=os.path.join(CURRENT_DIR, "template", "base"),
    destination_path="{{ input.project_dir }}",
    excludes=["*/__pycache__"],
)

copy_http_port_resource = ResourceMaker(
    name="copy-http-port-resource",
    inputs=inputs,
    should_execute="{{ input.is_http_port }}",
    upstreams=[copy_base_resource],
    replacements=replacements,
    template_path=os.path.join(CURRENT_DIR, "template", "http-port"),
    destination_path="{{ input.project_dir }}",
    excludes=["*/__pycache__"],
)

copy_custom_image_resource = ResourceMaker(
    name="copy-custom-image-resource",
    inputs=inputs,
    should_execute="{{ input.build_custom_image }}",
    upstreams=[copy_http_port_resource],
    replacements=replacements,
    template_path=os.path.join(CURRENT_DIR, "template", "build-custom-image"),
    destination_path="{{ input.project_dir }}",
    excludes=["*/__pycache__"],
)

copy_http_port_custom_image_resource = ResourceMaker(
    name="copy-http-port-custom-image-resource",
    inputs=inputs,
    should_execute="{{ input.is_http_port and input.build_custom_image }}",
    upstreams=[copy_custom_image_resource],
    replacements=replacements,
    template_path=os.path.join(
        CURRENT_DIR, "template", "http-port-build-custom-image"
    ),  # noqa
    destination_path="{{ input.project_dir }}",
    excludes=["*/__pycache__"],
)

copy_helm_resource = ResourceMaker(
    name="copy-helm-resource",
    inputs=inputs,
    should_execute="{{ input.use_helm }}",
    upstreams=[copy_http_port_custom_image_resource],
    replacements=replacements,
    template_path=os.path.join(CURRENT_DIR, "template", "use-helm"),
    destination_path="{{ input.project_dir }}",
    excludes=["*/__pycache__"],
)

copy_resource = CmdTask(
    name="copy-resource",
    upstreams=[
        copy_helm_resource,
    ],
    cmd="echo Resource copied",
)

register_module = create_register_module(
    module_path="_automate.generate_{{util.to_snake_case(input.template_name)}}.add",  # noqa
    alias="generate_{{util.to_snake_case(input.template_name)}}",
    inputs=[template_name_input],
    upstreams=[copy_resource],
)


@python_task(
    name="app-generator",
    group=project_add_group,
    upstreams=[register_module],
    inputs=inputs,
    runner=runner,
)
async def add_app_generator(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out("Success")
