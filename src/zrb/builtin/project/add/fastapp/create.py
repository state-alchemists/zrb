import os

from zrb.builtin.group import add_to_project_group
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.task.scaffolder import Scaffolder
from zrb.task.task import Task
from zrb.util.string.conversion import double_quote
from zrb.util.string.name import get_random_name

_DIR = os.path.dirname(__file__)


def _get_destination_path(ctx: AnySharedContext):
    return os.path.join(ctx.input["project-dir"], ctx.input["app-dir"])


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
            name="app-dir",
            description="App directory",
            prompt="App directory",
            default_str=lambda _: get_random_name(separator="_"),
        ),
    ],
    source_path=os.path.join(_DIR, "fastapp-template"),
    auto_render_source_path=False,
    destination_path=_get_destination_path,
    transform_content={"App Name": "{ctx.input['app-dir'].title()}"},
    retries=0,
)


@make_task(
    name="register-fastapp-automation",
    description="🌟 Create FastApp",
)
def register_fastapp_automation(ctx: AnyContext):
    project_dir_path = ctx.input["project-dir"]
    zrb_init_path = os.path.join(project_dir_path, "zrb_init.py")
    app_dir_path = ctx.input["app-dir"]
    app_automation_file_part = ", ".join(
        [double_quote(part) for part in [app_dir_path, "_zrb", "init.py"]]
    )
    with open(zrb_init_path, "+a") as f:
        f.write(f"load_file(os.path.join(_DIR, {app_automation_file_part}))\n")


scaffold_fastapp >> register_fastapp_automation

create_fastapp = add_to_project_group.add_task(
    Task(
        name="create-fastapp",
        description="🌟 Create FastApp",
    ),
    alias="create",
)
create_fastapp << [scaffold_fastapp]
