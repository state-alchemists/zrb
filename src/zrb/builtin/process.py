from zrb.builtin.group import process_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput

###############################################################################
# Task Definitions
###############################################################################

get_pid_by_port = CmdTask(
    name="get-pid-by-port",
    group=process_group,
    description="Get PID by port",
    inputs=[
        IntInput(
            name="port",
            shortcut="p",
            default="8080",
            description="Port to be checked",
            prompt="Port to be checked",
        )
    ],
    cmd="lsof -i :{{ input.port }} -n -P | awk 'NR>1 {print $2}'",
    checking_interval=3,
)
runner.register(get_pid_by_port)

get_pid_by_name = CmdTask(
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
runner.register(get_pid_by_name)
