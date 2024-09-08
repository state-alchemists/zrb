import json

from collections.abc import Mapping
from zrb.builtin.project.monorepo._config import MONOREPO_CONFIG, MONOREPO_CONFIG_FILE
from zrb.builtin.project.monorepo._group import project_monorepo_group
from zrb.task.decorator import python_task
from zrb.task.any_task import AnyTask
from zrb.task_input.str_input import StrInput
from zrb.runner import runner


@python_task(
    name="add",
    group=project_monorepo_group,
    inputs=[
        StrInput(
            name="alias",
            shortcut="a",
            prompt="Repo Alias",
            prompt_required=True
        ),
        StrInput(
            name="folder", shortcut="d",
            prompt="Directory",
            prompt_required=True
        ),
        StrInput(
            name="origin",
            shortcut="o",
            prompt="Repo URL",
            prompt_required=True
        ),
        StrInput(
            name="branch",
            shortcut="b",
            prompt="Repo Branch",
            prompt_required=True,
            default="main"
        ),
    ],
    description="Add repo to monorepo",
    runner=runner
)
def add_to_monorepo(*args, **kwargs):
    task: AnyTask = kwargs.get("_task")
    input_map: Mapping[str, str] = task.get_input_map()
    config = dict(MONOREPO_CONFIG)
    config[input_map.get("alias", "")] = {
        "folder": input_map.get("folder", ""),
        "branch": input_map.get("branch", ""),
        "origin": input_map.get("origin", ""),
    }
    with open(MONOREPO_CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=2)
