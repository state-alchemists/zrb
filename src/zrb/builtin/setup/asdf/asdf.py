import os

from zrb.builtin.group import setup_group
from zrb.builtin.setup.asdf.asdf_helper import (
    check_inexist_asdf_dir,
    get_install_prerequisites_cmd,
    setup_asdf_ps_config,
    setup_asdf_sh_config,
)
from zrb.builtin.setup.common_input import (
    package_manager_input,
    setup_bash_input,
    setup_powershell_input,
    setup_zsh_input,
    use_sudo_input,
)
from zrb.context.any_context import AnyContext
from zrb.task.cmd_task import CmdTask
from zrb.task.make_task import make_task

install_asdf_prerequisites = CmdTask(
    name="install-asdf-prerequisites",
    input=[package_manager_input, use_sudo_input],
    cmd=get_install_prerequisites_cmd,
    is_interactive=True,
)


download_asdf = CmdTask(
    name="download-asdf",
    cmd="git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.14.1",
    execute_condition=check_inexist_asdf_dir,
)
install_asdf_prerequisites >> download_asdf


@make_task(
    name="setup-asdf-on-bash",
    input=setup_bash_input,
    execute_condition='{ctx.input["setup-bash"]}',
    upstream=download_asdf,
)
def setup_asdf_on_bash(ctx: AnyContext):
    ctx.print("Configure asdf for bash")
    setup_asdf_sh_config(os.path.expanduser(os.path.join("~", ".bashrc")))


@make_task(
    name="setup-asdf-on-zsh",
    input=setup_zsh_input,
    execute_condition='{ctx.input["setup-zsh"]}',
    upstream=download_asdf,
)
def setup_asdf_on_zsh(ctx: AnyContext):
    ctx.print("Configure asdf for zsh")
    setup_asdf_sh_config(os.path.expanduser(os.path.join("~", ".zshrc")))


@make_task(
    name="setup-asdf-on-powershell",
    input=setup_powershell_input,
    execute_condition='{ctx.input["setup-powershell"]}',
    upstream=download_asdf,
)
def setup_asdf_on_powershell(ctx: AnyContext):
    ctx.print("Configure asdf for powershell")
    setup_asdf_ps_config(
        os.path.expanduser(os.path.join("~", ".config", "powershell", "profile.ps1"))
    )


@make_task(
    name="setup-asdf",
    description="🧰 Setup `asdf`.",
    group=setup_group,
    alias="asdf",
)
def setup_asdf(ctx: AnyContext):
    ctx.print("Setup complete, restart your terminal to continue")
    ctx.print("Some useful commands:")
    ctx.print("- asdf plugin add python")
    ctx.print("- asdf list all python")
    ctx.print("- asdf install python 3.12.0")
    ctx.print("- asdf global python 3.12.0")


setup_asdf << [setup_asdf_on_bash, setup_asdf_on_zsh, setup_asdf_on_powershell]
