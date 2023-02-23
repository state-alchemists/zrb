from zrb import (
    CmdTask, runner
)


my_task = CmdTask(
    name='my-task',
    description='my Task',
    cmd=[
        'echo my Task'
    ]
)
runner.register(my_task)
