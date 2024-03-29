import os

from zrb.builtin.devtool.install._group import dev_tool_install_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_kubectl = FlowTask(
    name="kubectl",
    group=dev_tool_install_group,
    description="Kubernetes CLI tool",
    steps=[
        CmdTask(
            name="install-kubectl",
            cmd_path=[
                os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_kubectl)
