import os

from zrb.builtin.devtool.install._group import devtool_install_group
from zrb.builtin.devtool.install._helper import write_config
from zrb.builtin.devtool.install._input import terminal_config_file_input
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task

_CURRENT_DIR = os.path.dirname(__file__)
_SHELL_SCRIPT_DIR = os.path.join(_CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_pulumi = FlowTask(
    name="pulumi",
    group=devtool_install_group,
    description="Universal infrastructure as code",
    inputs=[terminal_config_file_input],
    steps=[
        CmdTask(
            name="install-pulumi",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-pulumi",
            run=write_config(
                template_file=os.path.join(_CURRENT_DIR, "resource", "config.sh"),
                config_file="{{input.config_file}}",
            ),
        ),
    ],
    retry=0,
)
runner.register(install_pulumi)
