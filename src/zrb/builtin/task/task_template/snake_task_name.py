from zrb import (
    CmdTask, runner
)


snake_task_name = CmdTask(
    name='kebab-task-name',
    description='human readable task name',
    cmd=[
        'echo human readable task name'
    ]
)
runner.register(snake_task_name)
