import os

from zrb.builtin.generator.common.task_input import (
    app_name_input,
    entity_name_input,
    module_name_input,
    project_dir_input,
)
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import List
from zrb.task.any_task import AnyTask
from zrb.task.cmd_task import CmdTask

CURRENT_DIR = os.path.dirname(__file__)
CODEMOD_DIR = os.path.join(CURRENT_DIR, "nodejs", "codemod")

NAV_CONFIG_FILE_PATH = "{{input.project_dir}}/src/{{util.to_kebab_case(input.app_name)}}/src/frontend/src/lib/config/navData.ts"  # noqa
ENV_VAR_NAME = "navData"
NAV_TITLE = "{{util.to_pascal_case(input.entity_name)}}"
NAV_URL = "/{{util.to_kebab_case(input.module_name)}}/{{util.to_kebab_case(input.entity_name)}}"  # noqa
NAV_PERMISSION = "{{util.to_snake_case(input.module_name)}}:{{util.to_snake_case(input.entity_name)}}:get"  # noqa


@typechecked
def create_add_navigation_task(upstreams: List[AnyTask]) -> AnyTask:
    return CmdTask(
        name="add-navigation",
        inputs=[
            project_dir_input,
            app_name_input,
            module_name_input,
            entity_name_input,
        ],
        upstreams=upstreams,
        retry=0,
        cmd=f'node {CODEMOD_DIR}/dist/addNav.js "{NAV_CONFIG_FILE_PATH}" "{ENV_VAR_NAME}" "{NAV_TITLE}" "{NAV_URL}" "{NAV_PERMISSION}"',  # noqa
    )
