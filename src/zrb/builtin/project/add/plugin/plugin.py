import os

import tomlkit

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
from zrb.helper.util import to_kebab_case
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

CURRENT_DIR = os.path.dirname(__file__)


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
    module_path="_automate.{{util.to_snake_case(input.package_name)}}",
    inputs=[package_name_input],
    upstreams=[copy_resource, add_project_tasks],
)


@python_task(
    name="update-pyproject",
    upstreams=[copy_resource],
    inputs=[project_dir_input, package_name_input],
)
def update_pyproject(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    package_name = kwargs.get("package_name")
    kebab_package_name = to_kebab_case(package_name)
    with open(os.path.join(project_dir, "pyproject.toml"), "rb") as f:
        toml_dict = tomlkit.loads(f.read())
    toml_dict["tool"]["poetry"]["dependencies"][kebab_package_name] = {
        "path": f"./src/{kebab_package_name}"
    }
    with open(os.path.join(project_dir, "pyproject.toml"), "w") as f:
        f.write(tomlkit.dumps(toml_dict))


@python_task(
    name="plugin",
    group=project_add_group,
    description="Add plugin to project",
    upstreams=[register_module, update_pyproject],
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
