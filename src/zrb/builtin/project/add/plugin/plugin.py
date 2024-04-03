import os

from zrb.builtin.project._helper import (
    create_register_module,
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add._group import project_add_group
from zrb.builtin.project.add.plugin._input import (
    package_author_email_input,
    package_author_name_input,
    package_description_input,
    package_documentation_input,
    package_homepage_input,
    package_name_input,
    package_repository_input,
)
from zrb.builtin.project.add.project_task import add_project_tasks
from zrb.config.config import version
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

_CURRENT_DIR = os.path.dirname(__file__)


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
    template_path=os.path.join(_CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/__pycache__",
    ],
)

register_plugin = create_register_module(
    module_path="_automate.{{util.to_snake_case(input.package_name)}}",
    alias="_automate_{{util.to_snake_case(input.package_name)}}",
    inputs=[package_name_input],
    upstreams=[copy_resource, add_project_tasks],
    task_name="register-plugin",
)


@python_task(
    name="plugin",
    group=project_add_group,
    description="Add plugin to project",
    upstreams=[register_plugin],
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
async def add_plugin(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Plugin added", color="yellow"))
