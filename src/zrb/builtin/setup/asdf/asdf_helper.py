import os

from zrb.builtin.setup.common_input import get_install_packages_cmd
from zrb.builtin.setup.config_file_helper import append_config_block_if_missing
from zrb.context.any_context import AnyContext


def get_install_prerequisites_cmd(ctx: AnyContext) -> str:
    needs_coreutils = ctx.input["package-manager"] in ["brew", "spack"]
    packages = "coreutils curl git" if needs_coreutils else "curl git"
    return get_install_packages_cmd(ctx, packages)


def check_inexist_asdf_dir(_: AnyContext):
    asdf_dir = os.path.expanduser(os.path.join("~", ".asdf"))
    return not os.path.isdir(asdf_dir)


def setup_asdf_sh_config(file_path: str):
    append_config_block_if_missing(file_path, '. "$HOME/.asdf/asdf.sh"')


def setup_asdf_ps_config(file_path: str):
    append_config_block_if_missing(file_path, '. "$HOME/.asdf/asdf.ps1"')
