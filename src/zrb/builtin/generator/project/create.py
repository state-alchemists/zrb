import os

from zrb.builtin.generator.common.task_input import (
    project_author_email_input,
    project_author_name_input,
    project_description_input,
    project_dir_input,
    project_name_input,
)
from zrb.builtin.generator.project_task.task_factory import create_ensure_project_tasks
from zrb.builtin.group import project_group
from zrb.config.config import version
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Mapping
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker

CURRENT_DIR = os.path.dirname(__file__)
SYSTEM_USER = os.getenv("USER", "incognito")
IMAGE_DEFAULT_NAMESPACE = os.getenv(
    "PROJECT_IMAGE_DEFAULT_NAMESPACE", "docker.io/" + SYSTEM_USER
)

###############################################################################
# Replacement Mutator Definitions
###############################################################################


@typechecked
def copy_resource_replacement_mutator(
    task: ResourceMaker, replacements: Mapping[str, str]
) -> Mapping[str, str]:
    replacements["zrbBaseProjectDir"] = os.path.basename(
        replacements.get("zrbProjectDir", "")
    )
    if replacements.get("zrbProjectName", "") == "":
        replacements["zrbProjectName"] = replacements.get("zrbBaseProjectDir", "")
    return replacements


###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="validate",
    inputs=[project_dir_input],
    retry=0,
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    if os.path.isfile(os.path.join(project_dir, "zrb_init.py")):
        raise Exception(f"Project directory already exists: {project_dir}")


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        project_name_input,
        project_description_input,
        project_author_name_input,
        project_author_email_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbProjectDir": "{{input.project_dir}}",
        "zrbProjectName": "{{input.project_name}}",
        "zrbProjectDescription": "{{input.project_description}}",
        "zrbProjectAuthorName": "{{input.project_author_name}}",
        "zrbProjectAuthorEmail": "{{input.project_author_email}}",
        "zrbImageDefaultNamespace": IMAGE_DEFAULT_NAMESPACE,
        "zrbVersion": version,
    },
    replacement_mutator=copy_resource_replacement_mutator,
    template_path=os.path.join(CURRENT_DIR, "template"),
    destination_path="{{input.project_dir}}",
    excludes=[
        "*/__pycache__",
    ],
)

ensure_project_tasks = create_ensure_project_tasks(upstreams=[copy_resource])

create_project = CmdTask(
    name="create",
    group=project_group,
    upstreams=[ensure_project_tasks],
    inputs=[project_dir_input],
    cmd=[
        "set -e",
        'cd "{{input.project_dir}}"',
        "if [ ! -d .git ]",
        "then",
        "  echo Initialize project git repository",
        "  git init",
        "fi",
        'echo "Happy coding :)"',
    ],
)
runner.register(create_project)
