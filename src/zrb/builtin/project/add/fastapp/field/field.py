import asyncio
import os
from typing import Any

from zrb.builtin.project._helper import validate_existing_project_dir
from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add.fastapp._group import project_add_fastapp_group
from zrb.builtin.project.add.fastapp.app._input import app_name_input
from zrb.builtin.project.add.fastapp.crud._input import entity_name_input
from zrb.builtin.project.add.fastapp.field._helper import (
    inject_delete_page,
    inject_detail_page,
    inject_insert_page,
    inject_list_page,
    inject_repo,
    inject_schema,
    inject_test,
    inject_update_page,
)
from zrb.builtin.project.add.fastapp.field._input import (
    column_name_input,
    column_type_input,
)
from zrb.builtin.project.add.fastapp.module._input import module_name_input
from zrb.helper import util
from zrb.helper.accessories.color import colored
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.task import Task


@python_task(
    name="validate",
    inputs=[project_dir_input, app_name_input, module_name_input, entity_name_input],
    retry=0,
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
    if not os.path.exists(entity_path):
        raise Exception(f"Entity directory does not exist: {entity_path}")


@python_task(
    name="field",
    group=project_add_fastapp_group,
    description="Add Fastapp Field",
    inputs=[
        project_dir_input,
        app_name_input,
        module_name_input,
        entity_name_input,
        column_name_input,
        column_type_input,
    ],
    upstreams=[validate],
    runner=runner,
)
async def add_fastapp_field(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    project_dir = kwargs.get("project_dir", ".")
    app_name = kwargs.get("app_name")
    module_name = kwargs.get("module_name")
    entity_name = kwargs.get("entity_name")
    column_name = kwargs.get("column_name")
    column_type = kwargs.get("column_type")
    await asyncio.gather(
        asyncio.create_task(
            inject_test(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
                column_type=column_type,
            )
        ),
        asyncio.create_task(
            inject_schema(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
                column_type=column_type,
            )
        ),
        asyncio.create_task(
            inject_repo(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
                column_type=column_type,
            )
        ),
        asyncio.create_task(
            inject_list_page(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
            )
        ),
        asyncio.create_task(
            inject_detail_page(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
            )
        ),
        asyncio.create_task(
            inject_delete_page(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
            )
        ),
        asyncio.create_task(
            inject_update_page(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
                column_type=column_type,
            )
        ),
        asyncio.create_task(
            inject_insert_page(
                task=task,
                project_dir=project_dir,
                app_name=app_name,
                module_name=module_name,
                entity_name=entity_name,
                column_name=column_name,
                column_type=column_type,
            )
        ),
    )
    task.print_out(colored("Fastapp crud added", color="yellow"))
