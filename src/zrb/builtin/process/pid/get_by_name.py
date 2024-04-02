from zrb.builtin.process._group import process_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task_input.str_input import StrInput

get_process_pid_by_name = CmdTask(
    name="get-pid-by-name",
    group=process_group,
    description="Get PID by name",
    inputs=[
        StrInput(
            name="name",
            shortcut="n",
            default="python",
            description="Process name to be checked",
            prompt="Process name to be checked",
        )
    ],
    cmd="pgrep {{ input.name }}",
    checking_interval=3,
)
runner.register(get_process_pid_by_name)
