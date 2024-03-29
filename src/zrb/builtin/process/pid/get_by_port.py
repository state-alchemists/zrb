from zrb.builtin.process._group import process_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task_input.int_input import IntInput

get_process_pid_by_port = CmdTask(
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
runner.register(get_process_pid_by_port)
