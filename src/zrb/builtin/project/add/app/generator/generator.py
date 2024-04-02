import os

from zrb.builtin.project._helper import validate_existing_project_dir
from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add.app._group import project_add_app_group
from zrb.builtin.project.add.app.generator._helper import validate_existing_package
from zrb.builtin.project.add.app.generator._input import (
    generator_app_port_input,
    generator_base_image_input,
    generator_name_input,
    package_name_input,
)
from zrb.helper.accessories.color import colored
from zrb.helper.codemod.add_assert_resource import add_assert_resource
from zrb.helper.codemod.add_import_module import add_import_module
from zrb.helper.typing import Any
from zrb.helper.util import to_kebab_case, to_snake_case
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

_CURRENT_DIR = os.path.dirname(__file__)


@python_task(
    name="validate",
    inputs=[project_dir_input, package_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    package_name = kwargs.get("package_name")
    validate_existing_package(project_dir, package_name)


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        package_name_input,
        generator_name_input,
        generator_base_image_input,
        generator_app_port_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbPackageName": "{{input.package_name}}",
        "zrbGeneratorName": "{{input.generator_name}}",
        "zrbGeneratorBaseImage": "{{input.generator_base_image}}",
        "zrbGeneratorAppPort": "{{input.generator_app_port}}",
    },
    template_path=os.path.join(_CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/deployment/venv",
        "*/__pycache__",
    ],
)


@python_task(
    name="register-generator",
    inputs=[
        project_dir_input,
        package_name_input,
        generator_name_input,
    ],
    upstreams=[copy_resource],
)
def register_generator(*args: Any, **kwargs: Any):
    task = kwargs.get("_task")
    project_dir = kwargs.get("project_dir")
    package_name = kwargs.get("package_name")
    generator_name = kwargs.get("generator_name")
    kebab_package_name = to_kebab_case(package_name)
    snake_package_name = to_snake_case(package_name)
    snake_generator_name = to_snake_case(generator_name)
    package_init_path = os.path.join(
        project_dir, "src", kebab_package_name, "src", snake_package_name, "__init__.py"
    )
    with open(package_init_path, "r") as f:
        code = f.read()
    new_code = add_import_module(
        code=code,
        module_path=f"{snake_package_name}.{snake_generator_name}",
        alias=snake_generator_name,
    )
    new_code = add_assert_resource(code=new_code, resource=snake_generator_name)
    with open(package_init_path, "w") as f:
        f.write(new_code)
    task.print_out(colored("Register generator", color="yellow"))


@python_task(
    name="generator",
    group=project_add_app_group,
    description="Add app generator",
    upstreams=[
        register_generator,
    ],
    runner=runner,
)
async def add_app_generator(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Appp generator added", color="yellow"))
