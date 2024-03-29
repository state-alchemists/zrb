from zrb.builtin.ubuntu._group import ubuntu_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask

update_ubuntu = CmdTask(
    name="update",
    group=ubuntu_group,
    description="Update ubuntu",
    cmd=[
        "sudo apt update",
        "sudo apt upgrade -y",
    ],
    retry_interval=3,
    preexec_fn=None,
)
runner.register(update_ubuntu)
