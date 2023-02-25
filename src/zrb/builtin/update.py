from ..task.cmd_task import CmdTask
from ..runner import runner

update = CmdTask(
    name='update',
    description='Update zrb',
    cmd=[
        'pip install zrb -U',
    ],
    checking_interval=3
)
runner.register(update)
