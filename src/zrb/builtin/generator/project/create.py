from typing import Mapping
from ..._group import project_group
from ....task.cmd_task import CmdTask
from ....task.resource_maker import ResourceMaker
from ....runner import runner
from ....config.config import version
from .._common.input import project_dir_input, project_name_input
from ..project_task.task_factory import create_add_project_automation_task

import os

# Common definitions

current_dir = os.path.dirname(__file__)


def copy_resource_replacement_mutator(
    task: ResourceMaker, replacements: Mapping[str, str]
) -> Mapping[str, str]:
    replacements['baseProjectDir'] = os.path.basename(
        replacements.get('projectDir', '')
    )
    if replacements.get('projectName', '') == '':
        replacements['projectName'] = replacements.get('baseProjectDir', '')
    return replacements


# Task definitions

copy_resource = ResourceMaker(
    name='copy-resource',
    inputs=[
        project_dir_input,
        project_name_input
    ],
    replacements={
        'projectDir': '{{input.project_dir}}',
        'projectName': '{{input.project_name}}',
        'zrbVersion': version,
    },
    replacement_mutator=copy_resource_replacement_mutator,
    template_path=os.path.join(current_dir, 'template'),
    destination_path='{{input.project_dir}}',
    locks=['{{input.project_dir}}/zrb_init.py']
)

add_project_task = create_add_project_automation_task(
    upstreams=[copy_resource]
)

create_project = CmdTask(
    name='create',
    group=project_group,
    upstreams=[add_project_task],
    inputs=[project_dir_input],
    cmd=[
        'set -e',
        'cd "{{input.project_dir}}"',
        'if [ ! -d .git ]',
        'then',
        '  echo Initialize project git repository',
        '  git init',
        'fi',
        'echo "Happy coding :)"',
    ]
)
runner.register(create_project)
