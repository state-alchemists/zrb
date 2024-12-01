import os

from zrb.builtin.group import setup_group
from zrb.builtin.setup.common_input import package_manager_input, use_sudo_input
from zrb.builtin.setup.tmux.tmux_helper import get_install_tmux_cmd
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.cmd_task import CmdTask
from zrb.task.make_task import make_task

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
        default_str="~/.tmux.conf",
    ),
    description="🖥️ Setup `tmux`.",
    group=setup_group,
    alias="tmux",
)
def setup_tmux(ctx: AnyContext):
    with open(os.path.join(os.path.dirname(__file__), "tmux_config.sh"), "r") as f:
        tmux_config_template = f.read()
    tmux_config_file = os.path.expanduser(ctx.input["tmux-config"])
    tmux_config_dir = os.path.dirname(tmux_config_file)
    # Make sure config file exists
    os.makedirs(tmux_config_dir, exist_ok=True)
    if not os.path.isfile(tmux_config_file):
        with open(tmux_config_file, "w") as f:
            f.write("")
    with open(tmux_config_file, "r") as f:
        # config file already contain the config
        if tmux_config_template in f.read():
            return
    # Write config
    with open(tmux_config_file, "a") as f:
        f.write(f"\n{tmux_config_template}\n")
    ctx.print("Setup complete, restart your terminal to continue")


install_tmux >> setup_tmux
