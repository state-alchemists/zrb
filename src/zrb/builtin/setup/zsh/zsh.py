import os

from zrb.builtin.group import setup_group
from zrb.builtin.setup.common_input import package_manager_input, use_sudo_input
from zrb.builtin.setup.zsh.zsh_helper import get_install_zsh_cmd
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.cmd_task import CmdTask
from zrb.task.make_task import make_task
from zrb.util.file import read_file, write_file

install_zsh = CmdTask(
    name="install-zsh",
    input=[package_manager_input, use_sudo_input],
    cmd=get_install_zsh_cmd,
    is_interactive=True,
)

install_omz = CmdTask(
    name="install-omz",
    cmd='sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"',  # noqa
    upstream=install_zsh,
)

install_zinit = CmdTask(
    name="install-zinit",
    cmd='bash -c "$(curl --fail --show-error --silent --location https://raw.githubusercontent.com/zdharma-continuum/zinit/HEAD/scripts/install.sh)"',  # noqa
    upstream=install_zsh,
)


@make_task(
    name="setup-zsh",
    input=StrInput(
        name="zsh-config",
        description="zsh config file",
        prompt="zsh config file",
        default="~/.zshrc",
    ),
    upstream=[install_omz, install_zinit],
    description="💻 Setup `zsh`.",
    group=setup_group,
    alias="zsh",
)
def setup_zsh(ctx: AnyContext):
    zsh_config = read_file(os.path.join(os.path.dirname(__file__), "zsh_config.sh"))
    zsh_config_file = os.path.expanduser(ctx.input["zsh-config"])
    # Make sure config file exists
    if not os.path.isfile(zsh_config_file):
        write_file(zsh_config_file, "")
    content = read_file(zsh_config_file)
    if zsh_config in content:
        return
    # Write config
    write_file(zsh_config_file, [content, zsh_config, ""])
    ctx.print("Setup complete, restart your terminal to continue")
