import os

from zrb.builtin.devtool.install._group import devtool_install_group
from zrb.builtin.devtool.install._helper import write_config
from zrb.builtin.devtool.install._input import terminal_config_file_input
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task
from zrb.task_input.bool_input import BoolInput

_CURRENT_DIR = os.path.dirname(__file__)
_SHELL_SCRIPT_DIR = os.path.join(_CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_sdkman = FlowTask(
    name="sdkman",
    group=devtool_install_group,
    description="SDKMAN! is a tool for managing parallel versions of multiple Software Development Kits on most Unix based systems",  # noqa
    inputs=[
        BoolInput(
            name="install-java",
            description="Install Java",
            prompt="Do you want to install Java?",
            default=True,
        ),
        BoolInput(
            name="install-scala",
            description="Install Scala",
            prompt="Do you want to install Scala?",
            default=True,
        ),
        terminal_config_file_input,
    ],
    steps=[
        CmdTask(
            name="download-sdkman",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "download.sh"),
            ],
            preexec_fn=None,
        ),
        Task(
            name="configure-sdkman",
            run=write_config(
                template_file=os.path.join(_CURRENT_DIR, "resource", "config.sh"),
                config_file="{{input.config_file}}",
            ),
        ),
        CmdTask(
            name="finalize-sdkman-installation",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "finalize.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_sdkman)
