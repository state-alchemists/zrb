from .._group import create
from ...task.resource_maker import ResourceMaker
from ...task.cmd_task import CmdTask
from ...task_input.str_input import StrInput
from ...runner import runner
from ...helper.render_data.replacement_template import (
    Replacement
)
import os

current_dir = os.path.dirname(__file__)
copy_project_resource = ResourceMaker(
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
    replacements=Replacement().add_key_val(
            key='projectDir',
            value='input.project_dir'
        ).add_transformed_key_val(Replacement.ALL)(
            key='projectName',
            value=[
                'input.project_name',
                'os.path.basename(input.project_dir)'
            ]
        ).get(),
    template_path=os.path.join(current_dir, 'project_template'),
    destination_path='{{input.project_dir}}',
    scaffold_locks=['{{input.project_dir}}/zrb_init.py']
)

create_project = CmdTask(
    name='project',
    group=create,
    upstreams=[copy_project_resource],
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
runner.register(create_project)
