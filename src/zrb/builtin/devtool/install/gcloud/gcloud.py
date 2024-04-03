import os

from zrb.builtin.devtool.install._group import devtool_install_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask

_CURRENT_DIR = os.path.dirname(__file__)
_SHELL_SCRIPT_DIR = os.path.join(_CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_gcloud = FlowTask(
    name="gcloud",
    group=devtool_install_group,
    description="Gcloud CLI",
    steps=[
        CmdTask(
            name="install-gcloud",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        ),
    ],
    retry=0,
)
runner.register(install_gcloud)
