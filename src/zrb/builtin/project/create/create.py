import os

from ....input.str_input import StrInput
from ....task.scaffolder import Scaffolder
from ...group import project_group

_DIR = os.path.dirname(__file__)

create_project = project_group.add_task(
    Scaffolder(
        name="create-project",
        description="🌟 Create project",
        input=[
            StrInput(
                name="project-dir",
                description="Project directory",
                prompt="Project directory",
                default_str=lambda _: os.getcwd(),
            ),
            StrInput(
                name="project-name",
                description="Project name",
                prompt="Project name",
                default_str=lambda ctx: os.path.basename(ctx.input["project-dir"]),
            ),
        ],
        source_path=os.path.join(_DIR, "project-template"),
        auto_render_source_path=False,
        destination_path="{ctx.input['project-dir']}",
        transform_content={"Project Name": "{ctx.input['project-name'].title()}"},
        retries=0,
    ),
    alias="create",
)
