import os

from zrb.builtin.setup.common_input import get_install_packages_cmd
from zrb.context.any_context import AnyContext


def check_inexist_tpm_dir(_: AnyContext) -> bool:
    tpm_dir = os.path.expanduser(os.path.join("~", ".tmux", "plugins", "tpm"))
    return not os.path.isdir(tpm_dir)


def get_install_tmux_cmd(ctx: AnyContext) -> str:
    return get_install_packages_cmd(ctx, "tmux")
