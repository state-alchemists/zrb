from typing import Any
from zrb.builtin.generator.common.task_input import project_dir_input
from zrb.builtin.generator.common.helper import (
    validate_existing_project_dir, validate_inexisting_automation
)
from zrb.builtin.generator.common.task_factory import create_register_module
from zrb.builtin.group import project_add_group
from zrb.task.decorator import python_task
from zrb.task.task import Task
from zrb.task.cmd_task import CmdTask
from zrb.task.resource_maker import ResourceMaker
from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput
from zrb.task_input.bool_input import BoolInput
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

base_image_input = StrInput(
    name='base-image',
    shortcut='i',
    description='Template base image',
    prompt='Base image',
    default='python:3.10-slim'
)

default_app_port_input = IntInput(
    name='default-app-port',
    shortcut='p',
    description='Template default app port',
    prompt='Default app port',
    default=8080
)

build_custom_image_input = BoolInput(
    name='build-custom-image',
    description='Whether build custom image or not',
    prompt='Build custom image',
    default=True
)

is_container_only_input = BoolInput(
    name='is-container-only',
    description='Whether app only run as container or not',
    prompt='Is container only',
    default=False
)

is_http_port_input = BoolInput(
    name='is-http-port',
    description='Whether app run on top of HTTP protocol or not',
    prompt='Is app a web appp (run on top of HTTP protocol)',
    default=False
)

use_helm_chart_input = BoolInput(
    name='use-helm',
    description='Whether using helm for deployment or not',
    prompt=' '.join([
        'Use helm for deployment',
        '(Note: If you choose "No" or "False", you can ignore other',
        'helm related questions)',
    ]),
    default=False
)

helm_repo_name_input = StrInput(
    name='helm-repo-name',
    description='Helm repo name',
    prompt='Helm repo name',
    default='bitnami'
)

helm_repo_url_input = StrInput(
    name='helm-repo-url',
    description='Helm repo URL',
    prompt='Helm repo URL',
    default='https://charts.bitnami.com/bitnami'
)

helm_chart_name_input = StrInput(
    name='helm-chart-name',
    description='Helm chart name',
    prompt='Helm chart name',
    default='nginx'
)

helm_chart_version_input = StrInput(
    name='helm-chart-version',
    description='Helm chart version',
    prompt='Helm chart version',
    default='15.2.0'
)

download_helm_chart_input = BoolInput(
    name='download-helm-chart',
    description='Whether downloading helm chart or not',
    prompt='Download helm chart',
    default=True
)


###############################################################################
# Task Definitions
###############################################################################

validate_helm = CmdTask(
    name='validate-helm',
    inputs=[download_helm_chart_input],
    skip_execution='{{ not input.download_helm_chart}}',
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'check-helm.sh')
)


@python_task(
    name='validate',
    inputs=[
        project_dir_input,
        template_name_input,
        build_custom_image_input,
        is_container_only_input,
    ],
    upstreams=[validate_helm]
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get('project_dir')
    validate_existing_project_dir(project_dir)
    template_name = kwargs.get('template_name')
    validate_inexisting_automation(project_dir, template_name)
    is_container_only_input: bool = kwargs.get('is_container_only_input')
    build_custom_image_input: bool = kwargs.get('build_custom_image_input')
    if not is_container_only_input and not build_custom_image_input:
        raise Exception('Should build custom image in Non container-only app')


copy_base_resource = ResourceMaker(
    name='copy-base-resource',
    inputs=[
        project_dir_input,
        template_name_input,
        base_image_input,
        default_app_port_input,
    ],
    upstreams=[validate],
    replacements={
        'zrbMetaTemplateName': '{{input.template_name}}',
        'zrbMetaTemplateBaseImage': '{{input.base_image}}',
        'zrbMetaTemplateDefaultAppPort': '{{input.default_app_port}}',
    },
    template_path=os.path.join(CURRENT_DIR, 'template', 'base'),
    destination_path='{{ input.project_dir }}',
    excludes=['*/__pycache__']
)

copy_http_port_resource = ResourceMaker(
    name='copy-http-port-resource',
    inputs=[
        project_dir_input,
        is_http_port_input
    ],
    skip_execution='{{ not input.is_http_port }}',
    upstreams=[copy_base_resource],
    template_path=os.path.join(CURRENT_DIR, 'template', 'http_port'),
    destination_path='{{ input.project_dir }}',
    excludes=['*/__pycache__']
)

copy_container_only_resource = ResourceMaker(
    name='copy-non-container-only-resource',
    inputs=[
        project_dir_input,
        is_container_only_input
    ],
    skip_execution='{{ not input.is_container_only }}',
    upstreams=[copy_http_port_resource],
    template_path=os.path.join(CURRENT_DIR, 'template', 'container_only'),
    destination_path='{{ input.project_dir }}',
    excludes=['*/__pycache__']
)

# TODO: This override port/http checker, probably should use custom checker
copy_custom_image_resource = ResourceMaker(
    name='copy-custom-image-resource',
    inputs=[
        project_dir_input,
        build_custom_image_input
    ],
    skip_execution='{{ not input.build_custom_image }}',
    upstreams=[copy_container_only_resource],
    template_path=os.path.join(CURRENT_DIR, 'template', 'build_custom_image'),
    destination_path='{{ input.project_dir }}',
    excludes=['*/__pycache__']
)

copy_resource = CmdTask(
    name='copy-resource',
    upstreams=[copy_container_custom_image_resource],
    cmd='echo Resource copied'
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
    inputs=[
        template_name_input,
        default_app_port_input,
        is_http_port_input,
        base_image_input,
        build_custom_image_input,
        is_container_only_input,
        use_helm_chart_input,
        helm_repo_name_input,
        helm_repo_url_input,
        helm_chart_name_input,
        helm_chart_version_input,
        download_helm_chart_input,
    ],
    runner=runner
)
async def add_python_task(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    task.print_out('Success')
