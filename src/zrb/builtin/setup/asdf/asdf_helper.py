import os

from zrb.context.any_context import AnyContext
from zrb.util.file import read_file, write_file


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
    _setup_asdf_config(file_path, '. "$HOME/.asdf/asdf.sh"')


def setup_asdf_ps_config(file_path: str):
    _setup_asdf_config(file_path, '. "$HOME/.asdf/asdf.ps1"')


def _setup_asdf_config(file_path: str, asdf_config: str):
    if not os.path.isfile(file_path):
        write_file(file_path, "")
    content = read_file(file_path)
    if asdf_config in content:
        return
    write_file(file_path, [content, asdf_config, ""])
