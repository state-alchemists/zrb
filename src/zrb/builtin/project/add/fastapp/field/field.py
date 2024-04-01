import asyncio
import os

from zrb.builtin.project._helper import validate_existing_project_dir
from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add.fastapp._group import project_add_fastapp_group
from zrb.builtin.project.add.fastapp.app._input import app_name_input
from zrb.builtin.project.add.fastapp.crud._input import entity_name_input
from zrb.builtin.project.add.fastapp.field._helper import (
    add_column_to_delete_page,
    add_column_to_detail_page,
    add_column_to_insert_page,
    add_column_to_list_page,
    add_column_to_repo,
    add_column_to_schema,
    add_column_to_test,
    add_column_to_update_page,
)
from zrb.builtin.project.add.fastapp.field._input import (
    column_name_input,
    column_type_input,
)
from zrb.builtin.project.add.fastapp.module._input import module_name_input
from zrb.helper import util
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.task import Task


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
    column_type = kwargs.get("column_name")
    kebab_app_name = util.to_kebab_case(app_name)
    kebab_module_name = util.to_kebab_case(module_name)
    snake_module_name = util.to_snake_case(module_name)
    kebab_entity_name = util.to_kebab_case(entity_name)
    snake_entity_name = util.to_snake_case(entity_name)
    pascal_entity_name = util.to_pascal_case(entity_name)
    snake_column_name = util.to_snake_case(column_name)
    kebab_column_name = util.to_kebab_case(column_name)
    capitalized_human_readable_column_name = util.to_capitalized_human_readable(  # noqa
        column_name
    )
    await asyncio.gather(
        asyncio.create_task(
            add_column_to_test(
                task,
                project_dir,
                kebab_app_name,
                snake_module_name,
                snake_entity_name,
                snake_column_name,
                column_type,
            )
        ),
        asyncio.create_task(
            add_column_to_schema(
                task,
                project_dir,
                kebab_app_name,
                snake_module_name,
                snake_entity_name,
                pascal_entity_name,
                snake_column_name,
                column_type,
            )
        ),
        asyncio.create_task(
            add_column_to_repo(
                task,
                project_dir,
                kebab_app_name,
                snake_module_name,
                snake_entity_name,
                pascal_entity_name,
                snake_column_name,
                column_type,
            )
        ),
        asyncio.create_task(
            add_column_to_list_page(
                task,
                project_dir,
                kebab_app_name,
                kebab_module_name,
                kebab_entity_name,
                snake_column_name,
                capitalized_human_readable_column_name,
            )
        ),
        asyncio.create_task(
            add_column_to_detail_page(
                task,
                project_dir,
                kebab_app_name,
                kebab_module_name,
                kebab_entity_name,
                kebab_column_name,
                snake_column_name,
                capitalized_human_readable_column_name,
            )
        ),
        asyncio.create_task(
            add_column_to_delete_page(
                task,
                project_dir,
                kebab_app_name,
                kebab_module_name,
                kebab_entity_name,
                kebab_column_name,
                snake_column_name,
                capitalized_human_readable_column_name,
            )
        ),
        asyncio.create_task(
            add_column_to_update_page(
                task,
                project_dir,
                kebab_app_name,
                kebab_module_name,
                kebab_entity_name,
                kebab_column_name,
                snake_column_name,
                capitalized_human_readable_column_name,
            )
        ),
        asyncio.create_task(
            add_column_to_insert_page(
                task,
                project_dir,
                kebab_app_name,
                kebab_module_name,
                kebab_entity_name,
                kebab_column_name,
                snake_column_name,
                capitalized_human_readable_column_name,
            )
        ),
    )
    task.print_out(colored("Fastapp crud added", color="yellow"))
