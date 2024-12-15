import os

from zrb.builtin.group import add_to_project_group
from zrb.builtin.project.add.fastapp_input import app_name_input, project_dir_input
from zrb.builtin.project.add.fastapp_util import (
    get_zrb_init_import_code,
    get_zrb_init_load_app_name_task,
)
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task
from zrb.task.scaffolder import Scaffolder
from zrb.task.task import Task
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_snake_case
from zrb.util.string.name import get_random_name

_DIR = os.path.dirname(__file__)


@make_task(
    name="validate-create-fastapp",
    input=[project_dir_input, app_name_input],
    retries=0,
)
async def validate_create_fastapp(ctx: AnyContext):
    project_dir = ctx.input.project_dir
    if not os.path.isdir(project_dir):
        raise ValueError(f"Project directory not exists: {project_dir}")
    app_dir = os.path.join(project_dir, to_snake_case(ctx.input.app))
    if os.path.exists(app_dir):
        raise ValueError(f"Application directory already exists: {app_dir}")


scaffold_fastapp = Scaffolder(
    name="scaffold-fastapp",
    input=[
        project_dir_input,
        app_name_input,
    ],
    upstream=validate_create_fastapp,
    source_path=os.path.join(_DIR, "fastapp_template"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        ctx.input.project_dir, to_snake_case(ctx.input.app)
    ),
    transform_content={
        "fastapp_template": "{to_snake_case(ctx.input.app)}",
        "My App Name": "{ctx.input.app.title()}",
        "my-app-name": "{to_kebab_case(ctx.input.app)}",
        "my_app_name": "{to_snake_case(ctx.input.app)}",
        "MY_APP_NAME": "{to_snake_case(ctx.input.app).upper()}",
        "my-secure-password": lambda _: get_random_name(),
    },
    retries=0,
)


@make_task(
    name="update-fastapp-zrb-init",
    input=[
        project_dir_input,
        app_name_input,
    ],
    upstream=scaffold_fastapp,
    retries=0,
)
def update_fastapp_zrb_init(ctx: AnyContext):
    zrb_init_path = os.path.join(ctx.input.project_dir, "zrb_init.py")
    old_zrb_init_code = read_file(zrb_init_path)
    write_file(
        file_path=zrb_init_path,
        content=[
            get_zrb_init_import_code(old_zrb_init_code),
            old_zrb_init_code.strip(),
            get_zrb_init_load_app_name_task(ctx.input.app),
            "",
        ],
    )


add_fastapp_to_project = add_to_project_group.add_task(
    Task(
        name="add-fastapp",
        description="🚀 Add FastApp to project",
        upstream=update_fastapp_zrb_init,
        retries=0,
    ),
    alias="fastapp",
)
