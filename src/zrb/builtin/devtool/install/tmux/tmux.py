import os

from zrb.builtin.devtool.install._group import devtool_install_group
from zrb.builtin.devtool.install._helper import write_config
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

_CURRENT_DIR = os.path.dirname(__file__)
_SHELL_SCRIPT_DIR = os.path.join(_CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_tmux = FlowTask(
    name="tmux",
    group=devtool_install_group,
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
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-tmux",
            run=write_config(
                template_file=os.path.join(_CURRENT_DIR, "resource", "config.sh"),
                config_file="{{input.tmux_config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_tmux)
