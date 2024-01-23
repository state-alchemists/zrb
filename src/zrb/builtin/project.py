from zrb.builtin.group import project_group
from zrb.helper.env_map.fetch import fetch_env_map_from_group
from zrb.helper.typing import Any, Mapping
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task_input.bool_input import BoolInput

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="get-default-env",
    description="Get default values for project environments",
    inputs=[
        BoolInput(
            name="export",
            shortcut="e",
            description="Whether add export statement or not",
            default=True,
        )
    ],
    group=project_group,
    runner=runner,
)
async def get_default_env(*args: Any, **kwargs: Any) -> str:
    env_map: Mapping[str, str] = {}
    env_map = fetch_env_map_from_group(env_map, project_group)
    env_keys = list(env_map.keys())
    env_keys.sort()
    should_export = kwargs.get("export", True)
    export_prefix = "export " if should_export else ""
    return "\n".join([f"{export_prefix}{key}={env_map[key]}" for key in env_keys])
