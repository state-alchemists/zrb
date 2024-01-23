from zrb.runner import runner
from zrb.task.cmd_task import CmdTask

###############################################################################
# Task Definitions
###############################################################################

update = CmdTask(
    name="update",
    description="Update zrb",
    cmd="pip install zrb -U",
    checking_interval=3,
)
runner.register(update)
