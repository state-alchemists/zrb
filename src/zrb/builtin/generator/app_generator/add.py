from typing import Any
from zrb.builtin.generator.common.task_input import project_dir_input
from zrb.builtin.generator.common.helper import (
    validate_existing_project_dir, validate_inexisting_automation
)
from zrb.builtin.generator.common.task_factory import create_register_module
from zrb.builtin.group import project_add_group
from zrb.task.decorator import python_task
from zrb.task.task import Task
from zrb.task.resource_maker import ResourceMaker
from zrb.task_input.str_input import StrInput
from zrb.helper.accessories.name import get_random_name
from zrb.runner import runner

import os

CURRENT_DIR = os.path.dirname(__file__)


template_name_input = StrInput(
    name='template-name',
    shortcut='t',
    description='Template name',
    prompt='Template name',
    default=get_random_name()
)

template_base_image_input = StrInput(
    name='template-base-image',
    shortcut='i',
    prompt='Base image',
    default='python:3.10-slim'
)


###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='validate',
    inputs=[
        project_dir_input,
        template_name_input
    ]
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_existing_project_dir(project_dir)
    template_name = kwargs.get('template_name')
    validate_inexisting_automation(project_dir, template_name)


copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        template_name_input,
        template_base_image_input,
    ],
    upstreams=[validate],
    replacements={
        'zrbMetaTemplateName': '{{input.template_name}}',
        'zrbMetaTemplateBaseImage': '{{input.template_base_image}}',
    },
    template_path=os.path.join(CURRENT_DIR, 'template'),
    destination_path='{{ input.project_dir }}',
    excludes=[
        '*/__pycache__',
    ]
)

register_module = create_register_module(
    module_path='_automate.{{util.to_snake_case(input.template_name)}}.add',
    alias='{{util.to_snake_case(input.template_name)}}_add',
    inputs=[template_name_input],
    upstreams=[copy_resource]
)


@python_task(
    name='app-generator',
    group=project_add_group,
    upstreams=[register_module],
    runner=runner
)
async def add_python_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
