import os

from zrb.builtin.group import setup_dev_group
from zrb.builtin.setup.dev.asdf_helper import (
    check_asdf_dir,
    get_install_prerequisites_cmd,
    setup_asdf_ps_config,
    setup_asdf_sh_config,
)
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.option_input import OptionInput
from zrb.task.cmd_task import CmdTask
from zrb.task.make_task import make_task
from zrb.task.task import Task

install_asdf_prerequisites = CmdTask(
    name="install-asdf-prerequisites",
    input=[
        OptionInput(
            name="package-manager",
            description="Your package manager",
            prompt="Your package manager",
            options=["apt", "dnf", "pacman", "zypper", "brew", "spack"],
            default_str="apt",
        ),
        BoolInput(
            name="use-sudo",
            description="Use sudo or not",
            prompt="Need sudo",
            default_str="yes",
        ),
    ],
    cmd=get_install_prerequisites_cmd,
)


download_asdf = CmdTask(
    name="download-asdf",
    cmd="git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.14.1",
    execute_condition=check_asdf_dir,
)
install_asdf_prerequisites >> download_asdf


@make_task(
    name="setup-asdf-on-bash",
    input=BoolInput(
        name="setup-bash",
        description="Setup bash",
        prompt="Setup bash",
        default_str="yes",
    ),
    execute_condition='{ctx.input["setup_bash"]}',
    upstream=download_asdf,
)
def setup_asdf_on_bash(ctx: AnyContext):
    setup_asdf_sh_config(os.path.expanduser(os.path.join("~", ".bashrc")))


@make_task(
    name="setup-asdf-on-zsh",
    input=BoolInput(
        name="setup-zsh", description="Setup zsh", prompt="Setup zsh", default_str="yes"
    ),
    execute_condition='{ctx.input["setup_zsh"]}',
    upstream=download_asdf,
)
def setup_asdf_on_zsh(ctx: AnyContext):
    setup_asdf_sh_config(os.path.expanduser(os.path.join("~", ".zshrc")))


@make_task(
    name="setup-asdf-on-powershell",
    input=BoolInput(
        name="setup-powershell",
        description="Setup powershell",
        prompt="Setup powershell",
        default_str="yes",
    ),
    execute_condition='{ctx.input["setup_powershell"]}',
    upstream=download_asdf,
)
def setup_asdf_on_powershell(ctx: AnyContext):
    setup_asdf_ps_config(
        os.path.expanduser(os.path.join("~", ".config", "powershell", "profile.ps1"))
    )


setup_asdf = setup_dev_group.add_task(
    Task(name="setup-asdf", description="🧰 Setup `asdf`."), alias="asdf"
)
setup_asdf << [setup_asdf_on_bash, setup_asdf_on_zsh, setup_asdf_on_powershell]
