import os

from zrb.builtin.group import add_to_project_group
from zrb.builtin.project.add.fastapp.fastapp_input import (
    app_name_input,
    project_dir_input,
)
from zrb.builtin.project.add.fastapp.fastapp_util import (
    is_in_project_app_dir,
    is_project_zrb_init_file,
    update_project_zrb_init_file,
)
from zrb.content_transformer.content_transformer import ContentTransformer
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task
from zrb.task.scaffolder import Scaffolder
from zrb.task.task import Task
from zrb.util.string.conversion import to_snake_case
from zrb.util.string.name import get_random_name


@make_task(
    name="validate-add-fastapp",
    input=[project_dir_input, app_name_input],
    retries=0,
)
async def validate_add_fastapp(ctx: AnyContext):
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
    upstream=validate_add_fastapp,
    source_path=os.path.join(os.path.dirname(__file__), "fastapp_template"),
    render_source_path=False,
    destination_path="{ctx.input.project_dir}",
    transform_path={
        "my_app_name": "{to_snake_case(ctx.input.app)}",
    },
    transform_content=[
        # Common transformation (project_dir/app_dir/**/*)
        ContentTransformer(
            name="transform-app-dir",
            match=is_in_project_app_dir,
            transform={
                "My App Name": "{ctx.input.app.title()}",
                "my-app-name": "{to_kebab_case(ctx.input.app)}",
                "my_app_name": "{to_snake_case(ctx.input.app)}",
                "MY_APP_NAME": "{to_snake_case(ctx.input.app).upper()}",
                "my-secure-password": lambda _: get_random_name(),
                "my-secret-key": lambda _: get_random_name(),
            },
        ),
        # Register fastapp's tasks to project's zrb_init (project_dir/zrb_init.py)
        ContentTransformer(
            name="transform-zrb-init",
            match=is_project_zrb_init_file,
            transform=update_project_zrb_init_file,
        ),
    ],
    retries=0,
)

add_fastapp_to_project = add_to_project_group.add_task(
    Task(
        name="add-fastapp",
        description="🚀 Add FastApp to project",
        upstream=scaffold_fastapp,
        retries=0,
    ),
    alias="fastapp",
)
