import os

from zrb.builtin.devtool.install._group import dev_tool_install_group
from zrb.builtin.devtool.install._helper import write_config
from zrb.builtin.devtool.install._input import terminal_config_file_input
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_gvm = FlowTask(
    name="gvm",
    group=dev_tool_install_group,
    description="GVM provides interface to manage go version",
    inputs=[
        StrInput(
            name="go-default-version",
            description="Go default version",
            default="go1.21",
        ),
        terminal_config_file_input,
    ],
    steps=[
        CmdTask(
            name="download-gvm",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "download.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-gvm",
            run=write_config(
                template_file=os.path.join(CURRENT_DIR, "resource", "config.sh"),
                config_file="{{input.config_file}}",
            ),
        ),
        CmdTask(
            name="finalize-gvm-installation",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "finalize.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_gvm)