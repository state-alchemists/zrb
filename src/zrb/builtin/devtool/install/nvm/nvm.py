import os

from zrb.builtin.devtool.install._group import devtool_install_group
from zrb.builtin.devtool.install._helper import write_config
from zrb.builtin.devtool.install._input import terminal_config_file_input
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

_CURRENT_DIR = os.path.dirname(__file__)
_SHELL_SCRIPT_DIR = os.path.join(_CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_nvm = FlowTask(
    name="nvm",
    group=devtool_install_group,
    description="NVM allows you to quickly install and use different versions of node via the command line",  # noqa
    inputs=[
        StrInput(
            name="node-default-version",
            description="Node default version",
            default="node",
        ),
        terminal_config_file_input,
    ],
    steps=[
        CmdTask(
            name="download-nvm",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "download.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-nvm",
            run=write_config(
                template_file=os.path.join(_CURRENT_DIR, "resource", "config.sh"),
                config_file="{{input.config_file}}",
            ),
        ),
        CmdTask(
            name="finalize-nvm-installation",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "finalize.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_nvm)
