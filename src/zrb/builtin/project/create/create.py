import os

from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project._group import project_group
from zrb.builtin.project.create._helper import copy_resource_replacement_mutator
from zrb.builtin.project.create._input import (
    project_author_email_input,
    project_author_name_input,
    project_description_input,
    project_name_input,
)
from zrb.builtin.project.add.project_task import add_project_tasks
from zrb.config.config import version
from zrb.helper.typing import Any
from zrb.helper.accessories.color import colored
from zrb.runner import runner
from zrb.task.task import Task
from zrb.task.cmd_task import CmdTask
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR))), "shell-scripts"
)
SYSTEM_USER = os.getenv("USER", "incognito")
IMAGE_DEFAULT_NAMESPACE = os.getenv(
    "PROJECT_IMAGE_DEFAULT_NAMESPACE", "docker.io/" + SYSTEM_USER
)


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

_add_project_tasks = add_project_tasks.copy()
_add_project_tasks.add_upstream(copy_resource)

init_git = CmdTask(
    name="init-git",
    upstreams=[copy_resource],
    inputs=[project_dir_input],
    cmd_path=[
        os.path.join(SHELL_SCRIPTS_DIR, "_common-util.sh"),
        os.path.join(CURRENT_DIR, "init-git.sh")
    ]
)


@python_task(
    name="create",
    description="Create a new project",
    inputs=[
        project_dir_input,
        project_name_input,
        project_description_input,
        project_author_name_input,
        project_author_email_input,
    ],
    group=project_group,
    upstreams=[
        _add_project_tasks,
        init_git
    ],
)
def create_project(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project created", color="yellow"))
    task.print_out(colored("Happy coding :)", color="yellow"))


runner.register(create_project)
