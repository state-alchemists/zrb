import asyncio
import os

from zrb.builtin.generator.common.helper import validate_existing_project_dir
from zrb.builtin.generator.common.task_input import (
    app_name_input,
    entity_name_input,
    main_column_name_input,
    module_name_input,
    plural_entity_name_input,
    project_dir_input,
)
from zrb.builtin.generator.fastapp_crud.helper import (
    register_api,
    register_permission,
    register_rpc,
)
from zrb.builtin.generator.fastapp_crud.task_factory import create_add_navigation_task
from zrb.builtin.group import project_add_group
from zrb.helper import util
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

CURRENT_DIR = os.path.dirname(__file__)
CODEMOD_DIR = os.path.join(CURRENT_DIR, "nodejs", "codemod")

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="validate",
    inputs=[project_dir_input, app_name_input, module_name_input, entity_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    app_name = kwargs.get("app_name")
    module_name = kwargs.get("module_name")
    entity_name = kwargs.get("entity_name")
    snake_module_name = util.to_snake_case(module_name)
    snake_entity_name = util.to_snake_case(entity_name)
    automation_dir = os.path.join(
        project_dir, "_automate", util.to_snake_case(app_name)
    )
    if not os.path.exists(automation_dir):
        raise Exception(f"Automation directory does not exist: {automation_dir}")
    app_dir = os.path.join(project_dir, "src", f"{util.to_kebab_case(app_name)}")
    if not os.path.exists(app_dir):
        raise Exception(f"App directory does not exist: {app_dir}")
    module_path = os.path.join(app_dir, "src", "module", snake_module_name)
    if not os.path.exists(module_path):
        raise Exception(f"Module directory does not exist: {module_path}")
    entity_path = os.path.join(module_path, "entity", snake_entity_name)
    if os.path.exists(entity_path):
        raise Exception(f"Entity directory already exists: {entity_path}")


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
        entity_name_input,
        plural_entity_name_input,
        main_column_name_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbAppName": "{{input.app_name}}",
        "zrbModuleName": "{{input.module_name}}",
        "zrbEntityName": "{{input.entity_name}}",
        "zrbPluralEntityName": "{{input.plural_entity_name}}",
        "zrbColumnName": "{{input.column_name}}",
    },
    template_path=os.path.join(CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/__pycache__",
    ],
)


@python_task(
    name="register-crud",
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
        entity_name_input,
        plural_entity_name_input,
        main_column_name_input,
    ],
    upstreams=[
        copy_resource,
    ],
)
async def register_crud(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    project_dir = kwargs.get("project_dir", ".")
    app_name = kwargs.get("app_name")
    module_name = kwargs.get("module_name")
    entity_name = kwargs.get("entity_name")
    kebab_app_name = util.to_kebab_case(app_name)
    snake_module_name = util.to_snake_case(module_name)
    snake_entity_name = util.to_snake_case(entity_name)
    await asyncio.gather(
        asyncio.create_task(
            register_api(
                task, project_dir, kebab_app_name, snake_module_name, snake_entity_name
            )
        ),
        asyncio.create_task(
            register_rpc(
                task, project_dir, kebab_app_name, snake_module_name, snake_entity_name
            )
        ),
        asyncio.create_task(
            register_permission(
                task, project_dir, kebab_app_name, snake_module_name, snake_entity_name
            )
        ),
    )


prepare_codemod = CmdTask(
    name="prepare-codemod",
    cwd=CODEMOD_DIR,
    cmd=["npm install --save-dev", "node_modules/.bin/tsc"],
)

add_navigation = create_add_navigation_task(
    upstreams=[
        copy_resource,
        prepare_codemod,
    ]
)


@python_task(
    name="fastapp-crud",
    group=project_add_group,
    upstreams=[register_crud, add_navigation],
    runner=runner,
)
async def add_fastapp_crud(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out("Success")
