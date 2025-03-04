import os

from zrb.builtin.group import setup_group
from zrb.builtin.setup.common_input import package_manager_input, use_sudo_input
from zrb.builtin.setup.tmux.tmux_helper import get_install_tmux_cmd
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.cmd_task import CmdTask
from zrb.task.make_task import make_task
from zrb.util.file import read_file, write_file

install_tmux = CmdTask(
    name="install-tmux",
    input=[package_manager_input, use_sudo_input],
    cmd=get_install_tmux_cmd,
)


@make_task(
    name="setup-tmux",
    input=StrInput(
        name="tmux-config",
        description="Tmux config file",
        prompt="Tmux config file",
        default="~/.tmux.conf",
    ),
    description="📺 Setup `tmux`.",
    group=setup_group,
    alias="tmux",
)
def setup_tmux(ctx: AnyContext):
    tmux_config = read_file(os.path.join(os.path.dirname(__file__), "tmux_config.sh"))
    tmux_config_file = os.path.expanduser(ctx.input["tmux-config"])
    # Make sure config file exists
    if not os.path.isfile(tmux_config_file):
        write_file(tmux_config_file, "")
    content = read_file(tmux_config_file)
    if tmux_config in content:
        return
    # Write config
    write_file(tmux_config_file, [content, tmux_config, ""])
    ctx.print("Setup complete, restart your terminal to continue")


install_tmux >> setup_tmux
