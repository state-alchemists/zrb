from typing import List
from ....task.task import Task
from ....task.cmd_task import CmdTask
from .._common.input import (
    project_dir_input, app_name_input, module_name_input, entity_name_input,
)

import os

current_dir = os.path.dirname(__file__)
codemod_dir = os.path.join(current_dir, 'nodejs', 'codemod')

nav_config_file_path = '{{input.project_dir}}/src/{{util.to_kebab_case(input.app_name)}}/src/frontend/src/lib/config/navData.ts' # noqa
nav_var_name = 'navData'
nav_title = '{{util.to_pascal_case(input.entity_name)}}'
nav_url = '/{{util.to_kebab_case(input.module_name)}}/{{util.to_kebab_case(input.entity_name)}}' # noqa
nav_permission = '{{util.to_snake_case(input.module_name)}}:{{util.to_snake_case(input.entity_name)}}:get' # noqa


def create_add_navigation_task(upstreams: List[Task]) -> Task:
    return CmdTask(
        name='add-navigation',
        inputs=[
            project_dir_input,
            app_name_input,
            module_name_input,
            entity_name_input,
        ],
        upstreams=upstreams,
        retry=0,
        cmd=f'node {codemod_dir}/dist/addNav.js "{nav_config_file_path}" "{nav_var_name}" "{nav_title}" "{nav_url}" "{nav_permission}"' # noqa
    )
