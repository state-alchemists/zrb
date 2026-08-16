import os

from zrb.builtin.group import setup_group
from zrb.builtin.setup.common_input import package_manager_input, use_sudo_input
from zrb.builtin.setup.config_file_helper import append_config_block_if_missing
from zrb.builtin.setup.tmux.tmux_helper import get_install_tmux_cmd
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.cmd_task import CmdTask
from zrb.task.make_task import make_task
from zrb.util.file import read_file

install_tmux = CmdTask(
    name="install-tmux",
    input=[package_manager_input, use_sudo_input],
    cmd=get_install_tmux_cmd,
    is_interactive=True,
)


@make_task(
    name="setup-tmux",
    input=StrInput(
        name="tmux-config",
        description="Tmux config file",
        prompt="Tmux config file",
        default="~/.tmux.conf",
    ),
    upstream=install_tmux,
    description="📺 Setup `tmux`.",
    group=setup_group,
    alias="tmux",
)
def setup_tmux(ctx: AnyContext) -> None:
    tmux_config = read_file(os.path.join(os.path.dirname(__file__), "tmux_config.sh"))
    tmux_config_file = os.path.expanduser(ctx.input["tmux-config"])
    if not append_config_block_if_missing(tmux_config_file, tmux_config):
        return
    ctx.print("Setup complete, restart your terminal to continue")
