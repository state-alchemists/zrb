from zrb import (
    CmdTask, runner
)
from zrb.builtin._group import project_group


snake_task_name = CmdTask(
    name='kebab-task-name',
    description='human readable task name',
    group=project_group,
    cmd=[
        'echo human readable task name'
    ]
)
runner.register(snake_task_name)
