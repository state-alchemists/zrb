import os

from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add.fastapp.app._input import app_name_input
from zrb.builtin.project.add.fastapp.crud._input import entity_name_input
from zrb.builtin.project.add.fastapp.module._input import module_name_input
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import List
from zrb.task.any_task import AnyTask
from zrb.task.cmd_task import CmdTask

_CURRENT_DIR = os.path.dirname(__file__)
_CODEMOD_DIR = os.path.join(_CURRENT_DIR, "nodejs", "codemod")

_NAV_CONFIG_FILE_PATH = "{{input.project_dir}}/src/{{util.to_kebab_case(input.app_name)}}/src/frontend/src/lib/config/navData.ts"  # noqa
_ENV_VAR_NAME = "navData"
_NAV_TITLE = "{{util.to_pascal_case(input.entity_name)}}"
_NAV_URL = "/{{util.to_kebab_case(input.module_name)}}/{{util.to_kebab_case(input.entity_name)}}"  # noqa
_NAV_PERMISSION = "{{util.to_snake_case(input.module_name)}}:{{util.to_snake_case(input.entity_name)}}:get"  # noqa


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
        cmd=f'node {_CODEMOD_DIR}/dist/addNav.js "{_NAV_CONFIG_FILE_PATH}" "{_ENV_VAR_NAME}" "{_NAV_TITLE}" "{_NAV_URL}" "{_NAV_PERMISSION}"',  # noqa
    )
