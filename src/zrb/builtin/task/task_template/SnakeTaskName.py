from zrb import (
    CmdTask, runner
)


SnakeTaskName = CmdTask(
    name='KebabTaskName',
    description='HumanTaskName',
    cmd=[
        'echo HumanTaskName'
    ]
)
runner.register(SnakeTaskName)
