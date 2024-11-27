import os

from zrb.builtin.group import add_to_project_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.task.scaffolder import Scaffolder
from zrb.task.task import Task
from zrb.util.string.conversion import double_quote
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
            name="app-name",
            description="App name",
            prompt="App name",
            default_str=lambda _: get_random_name(separator="_"),
        ),
    ],
    source_path=os.path.join(_DIR, "fastapp_template"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        ctx.input["project-dir"], ctx.input["app-name"]
    ),
    transform_content={
        "fastapp_template": "{to_snake_case(ctx.input['app-name'])}",
        "App Name": "{ctx.input['app-name'].title()}",
        "App name": "{ctx.input['app-name'].capitalize()}",
        "app-name": "{to_kebab_case(ctx.input['app-name'])}",
        "app_name": "{to_snake_case(ctx.input['app-name'])}",
        "APP_NAME": "{to_snake_case(ctx.input['app-name']).upper()}",
        "secure-password": lambda _: get_random_name(),
    },
    retries=0,
)


@make_task(
    name="register-fastapp-automation",
)
def register_fastapp_automation(ctx: AnyContext):
    project_dir_path = ctx.input["project-dir"]
    zrb_init_path = os.path.join(project_dir_path, "zrb_init.py")
    app_dir_path = ctx.input["app-name"]
    app_automation_file_part = ", ".join(
        [double_quote(part) for part in [app_dir_path, "_zrb", "main.py"]]
    )
    with open(zrb_init_path, "+a") as f:
        f.write(f"load_file(os.path.join(_DIR, {app_automation_file_part}))\n")


scaffold_fastapp >> register_fastapp_automation

add_fastapp_to_project = add_to_project_group.add_task(
    Task(
        name="add-fastapp",
        description="🚀 Add FastApp to project",
    ),
    alias="fastapp",
)
add_fastapp_to_project << [register_fastapp_automation]
