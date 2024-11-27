import os

from zrb.builtin.group import project_group
from zrb.input.str_input import StrInput
from zrb.task.scaffolder import Scaffolder
from zrb.task.task import Task

_DIR = os.path.dirname(__file__)

scaffold_project = Scaffolder(
    name="scaffold-project",
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
    render_source_path=False,
    destination_path="{ctx.input['project-dir']}",
    transform_content={"Project Name": "{ctx.input['project-name'].title()}"},
    retries=0,
)

create_project = project_group.add_task(
    Task(
        name="create-project",
        description="🌟 Create project",
    ),
    alias="create",
)
scaffold_project >> create_project
