import os

from .....context.any_shared_context import AnySharedContext
from .....input.str_input import StrInput
from .....task.scaffolder import Scaffolder
from .....util.string.name import get_random_name
from ....group import fastapp_group

_DIR = os.path.dirname(__file__)


def _get_destination_path(ctx: AnySharedContext):
    return os.path.join(ctx.input["project-dir"], ctx.input["app-dir"])


create_fastapp = fastapp_group.add_task(
    Scaffolder(
        name="create-fastapp",
        description="🌟 Create project",
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
    ),
    alias="create",
)
