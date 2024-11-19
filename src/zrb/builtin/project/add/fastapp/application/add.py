import os

from ......context.any_context import AnyContext
from ......input.str_input import StrInput
from ......task.make_task import make_task
from ......task.scaffolder import Scaffolder
from ......task.task import Task
from ......util.string.conversion import double_quote
from ......util.string.name import get_random_name
from .....group import add_fastapp_to_project_group

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
    source_path=os.path.join(_DIR, "app_name"),
    auto_render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        ctx.input["project-dir"], ctx.input["app-name"]
    ),
    transform_content={
        "App Name": "{ctx.input['app-name'].title()}",
        "App name": "{ctx.input['app-name'].capitalize()}",
        "app-name": "{to_kebab_case(ctx.input['app-name'])}",
        "app_name": "{to_snake_case(ctx.input['app-name'])}",
        "APP_NAME": "{to_snake_case(ctx.input['app-name']).upper()}",
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
        [double_quote(part) for part in [app_dir_path, "_zrb_init.py"]]
    )
    with open(zrb_init_path, "+a") as f:
        f.write(f"load_file(os.path.join(_DIR, {app_automation_file_part}))\n")


scaffold_fastapp >> register_fastapp_automation

add_fastapp_to_project = add_fastapp_to_project_group.add_task(
    Task(
        name="add-fastapp-app",
        description="🌟 Create FastApp Application",
    ),
    alias="application",
)
add_fastapp_to_project << [register_fastapp_automation]
