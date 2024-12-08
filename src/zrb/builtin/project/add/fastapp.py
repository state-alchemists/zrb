import os

from zrb.builtin.group import add_to_project_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.task.scaffolder import Scaffolder
from zrb.task.task import Task
from zrb.util.string.conversion import double_quote, to_snake_case
from zrb.util.string.name import get_random_name

_DIR = os.path.dirname(__file__)


scaffold_fastapp = Scaffolder(
    name="scaffold-fastapp",
    input=[
        StrInput(
            name="project-dir",
            description="Project directory",
            prompt="Project directory",
            default_str=lambda _: os.getcwd(),
        ),
        StrInput(
            name="app",
            description="App name",
            prompt="App name",
        ),
    ],
    source_path=os.path.join(_DIR, "fastapp_template"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(ctx.input["project-dir"], ctx.input.app),
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
    name="register-fastapp-automation",
    retries=0,
)
def register_fastapp_automation(ctx: AnyContext):
    project_dir_path = ctx.input["project-dir"]
    zrb_init_path = os.path.join(project_dir_path, "zrb_init.py")
    app_dir_path = ctx.input.app
    app_name = to_snake_case(ctx.input.app)
    with open(zrb_init_path, "r") as f:
        file_content = f.read().strip()
    # Assemble new content
    new_content_list = [file_content]
    # Check if import load_file is exists, if not exists, add
    import_load_file_script = "from zrb import load_file"
    if import_load_file_script not in file_content:
        new_content_list = [import_load_file_script] + new_content_list
    # Add fastapp-automation script
    automation_file_part = ", ".join(
        [double_quote(part) for part in [app_dir_path, "_zrb", "main.py"]]
    )
    new_content_list = new_content_list + [
        f"{app_name} = load_file(os.path.join(_DIR, {automation_file_part}))",
        f"assert {app_name}",
        "",
    ]
    new_content = "\n".join(new_content_list)
    # Write new content
    with open(zrb_init_path, "w") as f:
        f.write(new_content)


scaffold_fastapp >> register_fastapp_automation

add_fastapp_to_project = add_to_project_group.add_task(
    Task(
        name="add-fastapp",
        description="🚀 Add FastApp to project",
        retries=0,
    ),
    alias="fastapp",
)
add_fastapp_to_project << [register_fastapp_automation]
