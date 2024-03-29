import os

from zrb.builtin.devtool.install._group import dev_tool_install_group
from zrb.builtin.devtool.install._helper import write_config
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_tmux = FlowTask(
    name="tmux",
    group=dev_tool_install_group,
    description="Terminal multiplexer",
    inputs=[
        StrInput(
            name="tmux-config-file",
            shortcut="c",
            prompt="Tmux config file",
            default="~/.tmux.conf",
        )
    ],
    steps=[
        CmdTask(
            name="install-tmux",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-tmux",
            run=write_config(
                template_file=os.path.join(CURRENT_DIR, "resource", "config.sh"),
                config_file="{{input.tmux_config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_tmux)
