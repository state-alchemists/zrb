import os

from .....context.any_context import AnyContext
from .....context.any_shared_context import AnySharedContext
from .....input.str_input import StrInput
from .....task.make_task import make_task
from .....task.scaffolder import Scaffolder
from .....util.string.name import get_random_name
from ....group import fastapp_group

_DIR = os.path.dirname(__file__)


def _get_destination_path(ctx: AnySharedContext):
    return os.path.join(ctx.input["project-dir"], ctx.input["app-dir"])


scaffold = Scaffolder(
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
    group=fastapp_group,
    alias="create",
)
def create_fastapp(ctx: AnyContext):
    project_dir_path = ctx.input["project-dir"]
    zrb_init_path = os.path.join(project_dir_path, "zrb_init.py")
    app_dir_path = ctx.input["app-dir"]
    app_automation_file_path = os.path.join(app_dir_path, "_zrb", "init.py")
    with open(zrb_init_path, "+a") as f:
        f.write(f'load_file(os.path.join(_DIR, "{app_automation_file_path}"))\n')


scaffold >> create_fastapp
