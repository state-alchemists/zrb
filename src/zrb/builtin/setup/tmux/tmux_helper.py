import os

from zrb.context.any_context import AnyContext


def check_inexist_tpm_dir(_: AnyContext) -> bool:
    tpm_dir = os.path.expanduser(os.path.join("~", ".tmux", "plugins", "tpm"))
    return not os.path.isdir(tpm_dir)


def get_install_tmux_cmd(ctx: AnyContext) -> str:
    package_manager: str = ctx.input["package-manager"]
    if package_manager == "pacman":
        cmd = f"{package_manager} -S tmux"
    else:
        cmd = f"{package_manager} install tmux"
    use_sudo: bool = ctx.input["use-sudo"]
    if use_sudo:
        return f"sudo {cmd}"
    return cmd
