import os

from zrb.builtin.generator.common.helper import (
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.generator.common.task_factory import create_register_module
from zrb.builtin.generator.common.task_input import (
    package_author_email_input,
    package_author_name_input,
    package_description_input,
    package_documentation_input,
    package_homepage_input,
    package_name_input,
    package_repository_input,
    project_dir_input,
)
from zrb.builtin.group import project_add_group
from zrb.config.config import version
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

CURRENT_DIR = os.path.dirname(__file__)


###############################################################################
# Task Definitions
###############################################################################


@python_task(name="validate", inputs=[project_dir_input, package_name_input])
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    package_name = kwargs.get("package_name")
    validate_inexisting_automation(project_dir, package_name)


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        package_name_input,
        package_description_input,
        package_homepage_input,
        package_repository_input,
        package_documentation_input,
        package_author_name_input,
        package_author_email_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbPackageName": "{{input.package_name}}",
        "zrbPackageDescription": "{{input.package_description}}",
        "zrbPackageHomepage": "{{input.package_homepage}}",
        "zrbPackageRepository": "{{input.package_repository}}",
        "zrbPackageDocumentation": "{{input.package_documentation}}",
        "zrbPackageAuthorName": "{{input.package_author_name}}",
        "zrbPackageAuthorEmail": "{{input.package_author_email}}",
        "zrbVersion": version,
    },
    template_path=os.path.join(CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/__pycache__",
    ],
)

register_module = create_register_module(
    module_path="_automate.{{util.to_snake_case(input.package_name)}}.local",
    alias="{{util.to_snake_case(input.package_name)}}_local",
    inputs=[package_name_input],
    upstreams=[copy_resource],
)


@python_task(
    name="pip-package",
    group=project_add_group,
    upstreams=[register_module],
    inputs=[
        project_dir_input,
        package_name_input,
        package_description_input,
        package_homepage_input,
        package_repository_input,
        package_documentation_input,
        package_author_name_input,
        package_author_email_input,
    ],
    runner=runner,
)
async def add_pip_package(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out("Success")
