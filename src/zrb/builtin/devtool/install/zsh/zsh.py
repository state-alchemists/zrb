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


install_zsh = FlowTask(
    name="zsh",
    group=devtool_install_group,
    description="Zsh terminal + oh-my-zsh + zdharma",
    inputs=[
        StrInput(
            name="zsh-config-file",
            shortcut="c",
            prompt="Zsh config file",
            default="~/.zshrc",
        )
    ],
    steps=[
        CmdTask(
            name="install-zsh",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-zsh",
            run=write_config(
                template_file=os.path.join(_CURRENT_DIR, "resource", "config.sh"),
                config_file="{{input.zsh_config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_zsh)
