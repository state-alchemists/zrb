from zrb.context.any_context import AnyContext


def get_install_zsh_cmd(ctx: AnyContext) -> str:
    package_manager: str = ctx.input["package-manager"]
    if package_manager == "pacman":
        cmd = f"{package_manager} -S zsh"
    else:
        cmd = f"{package_manager} install zsh"
    use_sudo: bool = ctx.input["use-sudo"]
    if use_sudo:
        return f"sudo {cmd}"
    return cmd
