from .._group import project_group
from ...helper.middlewares.replacement import (
    coalesce, add_pascal_key, add_base_name_key
)
from ...task.cmd_task import CmdTask
from ...task.resource_maker import ResourceMaker
from ...task_input.str_input import StrInput
from ...runner import runner
from ...config.config import version

import os

# Common definitions

current_dir = os.path.dirname(__file__)

# Task definitions

project_copy_resource_task = ResourceMaker(
    name='copy-resource',
    inputs=[
        StrInput(
            name='project-dir',
            prompt='Project directory',
            default='.'
        ),
        StrInput(
            name='project-name',
            prompt='Project name (can be empty)',
            default=''
        ),
    ],
    replacements={
        'projectDir': '{{input.project_dir}}',
        'projectName': '{{input.project_name}}',
        'zrbVersion': version,
    },
    replacement_middlewares=[
        add_base_name_key('baseProjectDir', 'projectDir'),
        coalesce('projectName', ['baseProjectDir']),
        add_pascal_key('PascalProjectName', 'projectName')
    ],
    template_path=os.path.join(current_dir, 'project_template'),
    destination_path='{{input.project_dir}}',
    scaffold_locks=['{{input.project_dir}}/zrb_init.py']
)

project_create_task = CmdTask(
    name='create',
    group=project_group,
    upstreams=[project_copy_resource_task],
    inputs=[
        StrInput(name='project-dir', prompt='Project directory', default='.')
    ],
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
runner.register(project_create_task)
