import asyncio
import os

from zrb.builtin.project._helper import validate_existing_project_dir
from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add.fastapp._group import project_add_fastapp_group
from zrb.builtin.project.add.fastapp.app._input import app_name_input
from zrb.builtin.project.add.fastapp.module._helper import (
    append_all_disabled_env,
    append_all_enabled_env,
    append_deployment_template_env,
    append_src_template_env,
    create_app_config,
    create_microservice_config,
    register_migration,
    register_module,
)
from zrb.builtin.project.add.fastapp.module._input import module_name_input
from zrb.helper import util
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

_CURRENT_DIR = os.path.dirname(__file__)


@python_task(
    name="validate",
    inputs=[project_dir_input, app_name_input, module_name_input],
    retry=0,
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    app_name = kwargs.get("app_name")
    module_name = kwargs.get("module_name")
    snake_module_name = util.to_snake_case(module_name)
    automation_dir = os.path.join(
        project_dir, "_automate", util.to_snake_case(app_name)
    )
    if not os.path.exists(automation_dir):
        raise Exception(f"Automation directory does not exist: {automation_dir}")
    app_dir = os.path.join(project_dir, "src", f"{util.to_kebab_case(app_name)}")
    if not os.path.exists(app_dir):
        raise Exception(f"App directory does not exist: {app_dir}")
    module_path = os.path.join(app_dir, "src", "module", snake_module_name)
    if os.path.exists(module_path):
        raise Exception(f"Module directory already exists: {module_path}")


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbAppName": "{{input.app_name}}",
        "zrbModuleName": "{{input.module_name}}",
    },
    template_path=os.path.join(_CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/__pycache__",
    ],
)


@python_task(
    name="module",
    group=project_add_fastapp_group,
    description="Add Fastapp module",
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
    ],
    upstreams=[copy_resource],
    runner=runner,
)
async def add_fastapp_module(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    project_dir = kwargs.get("project_dir", ".")
    app_name = kwargs.get("app_name")
    module_name = kwargs.get("module_name")
    kebab_app_name = util.to_kebab_case(app_name)
    snake_app_name = util.to_snake_case(app_name)
    kebab_module_name = util.to_kebab_case(module_name)
    snake_module_name = util.to_snake_case(module_name)
    upper_snake_module_name = snake_module_name.upper()
    await asyncio.gather(
        asyncio.create_task(
            create_microservice_config(
                task,
                project_dir,
                kebab_app_name,
                snake_app_name,
                kebab_module_name,
                snake_module_name,
                upper_snake_module_name,
            )
        ),
        asyncio.create_task(
            register_module(task, project_dir, kebab_app_name, snake_module_name)
        ),
        asyncio.create_task(
            register_migration(task, project_dir, kebab_app_name, snake_module_name)
        ),
        asyncio.create_task(
            create_app_config(
                task,
                project_dir,
                kebab_app_name,
                snake_module_name,
                upper_snake_module_name,
            )
        ),
        asyncio.create_task(
            append_all_enabled_env(
                task, project_dir, kebab_app_name, upper_snake_module_name
            )
        ),
        asyncio.create_task(
            append_all_disabled_env(
                task, project_dir, kebab_app_name, upper_snake_module_name
            )
        ),
        asyncio.create_task(
            append_src_template_env(
                task, project_dir, kebab_app_name, upper_snake_module_name
            )
        ),
        asyncio.create_task(
            append_deployment_template_env(
                task, project_dir, kebab_app_name, upper_snake_module_name
            )
        ),
    )
    task.print_out(colored("Fastapp crud added", color="yellow"))
