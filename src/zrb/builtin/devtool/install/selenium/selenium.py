import os

from zrb.builtin.devtool.install._group import dev_tool_install_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_selenium = FlowTask(
    name="selenium",
    group=dev_tool_install_group,
    description="Selenium + Chrome web driver",
    steps=[
        CmdTask(
            name="install-selenium",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        )
    ],
)
runner.register(install_selenium)
