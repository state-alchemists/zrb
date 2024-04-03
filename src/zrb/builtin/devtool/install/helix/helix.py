import os

from zrb.builtin.devtool.install._group import devtool_install_group
from zrb.builtin.devtool.install._helper import write_config
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask
from zrb.task.task import Task

_CURRENT_DIR = os.path.dirname(__file__)
_SHELL_SCRIPT_DIR = os.path.join(_CURRENT_DIR, "..", "..", "..", "..", "shell-scripts")

install_helix = FlowTask(
    name="helix",
    group=devtool_install_group,
    description="Post modern text editor",
    steps=[
        CmdTask(
            name="install-helix",
            cmd_path=[
                os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                os.path.join(_CURRENT_DIR, "install.sh"),
            ],
            preexec_fn=None,
        ),
        [
            Task(
                name="create-helix-theme",
                run=write_config(
                    template_file=os.path.join(
                        _CURRENT_DIR,
                        "helix",
                        "resource",
                        "themes",
                        "gruvbox_transparent.toml",  # noqa
                    ),
                    config_file="~/.config/helix/themes/gruvbox_transparent.toml",  # noqa
                    remove_old_config=True,
                ),
            ),
            Task(
                name="configure-helix",
                run=write_config(
                    template_file=os.path.join(
                        _CURRENT_DIR, "helix", "resource", "config.toml"
                    ),
                    config_file="~/.config/helix/config.toml",
                    remove_old_config=True,
                ),
            ),
            CmdTask(
                name="install-language-server",
                cmd_path=[
                    os.path.join(_SHELL_SCRIPT_DIR, "_common-util.sh"),
                    os.path.join(_CURRENT_DIR, "install-language-server.sh"),
                ],
                preexec_fn=None,
            ),
        ],
    ],
    retry=0,
)
runner.register(install_helix)
