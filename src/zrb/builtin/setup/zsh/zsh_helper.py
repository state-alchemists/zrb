import os

from zrb.builtin.setup.common_input import get_install_packages_cmd
from zrb.context.any_context import AnyContext


def check_inexist_omz_dir(_: AnyContext) -> bool:
    omz_dir = os.path.expanduser(os.path.join("~", ".oh-my-zsh"))
    return not os.path.isdir(omz_dir)


def check_inexist_zinit_dir(_: AnyContext) -> bool:
    xdg_data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
        os.path.join("~", ".local", "share")
    )
    zinit_dir = os.path.join(xdg_data_home, "zinit", "zinit.git")
    return not os.path.isdir(zinit_dir)


def get_install_zsh_cmd(ctx: AnyContext) -> str:
    return get_install_packages_cmd(ctx, "zsh")
