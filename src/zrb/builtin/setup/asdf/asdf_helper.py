import os

from zrb.builtin.setup.config_file_helper import append_config_block_if_missing
from zrb.context.any_context import AnyContext


def get_install_prerequisites_cmd(ctx: AnyContext) -> str:
    package_manager: str = ctx.input["package-manager"]
    if package_manager in ["brew", "spack"]:
        cmd = f"{package_manager} install coreutils curl git"
    elif package_manager == "pacman":
        cmd = f"{package_manager} -S curl git"
    else:
        cmd = f"{package_manager} install curl git"
    use_sudo: bool = ctx.input["use-sudo"]
    if use_sudo:
        return f"sudo {cmd}"
    return cmd


def check_inexist_asdf_dir(_: AnyContext):
    asdf_dir = os.path.expanduser(os.path.join("~", ".asdf"))
    return not os.path.isdir(asdf_dir)


def setup_asdf_sh_config(file_path: str):
    append_config_block_if_missing(file_path, '. "$HOME/.asdf/asdf.sh"')


def setup_asdf_ps_config(file_path: str):
    append_config_block_if_missing(file_path, '. "$HOME/.asdf/asdf.ps1"')
