from .subcommand import SubCommand


def make_zsh_completion_script(cmd: str, subcommands: list[SubCommand]):
    zsh_script = [
        "_zrb_complete() {",
        "    local -a subcommands",
        "",
        "    # Initialize subcommands",
        "    subcommands=()",
        ""
    ]
    # Iterate through command completions to generate conditions
    for index, subcommand in enumerate(subcommands):
        _add_zsh_completion_conditions(
            zsh_script=zsh_script,
            path=subcommand.paths,
            nexts=subcommand.nexts,
            depth=len(subcommand.paths),
            is_first=index == 0,
            is_last=index == (len(subcommands) - 1),
        )
    # Last part
    zsh_script += [
        "",
        "    # Provide the completion suggestions",
        "    _describe 'subcommand' subcommands",
        "}",
        "",
        "# Register the completion function",
        "compdef _zrb_complete zrb"
    ]
    return "\n".join(zsh_script)


def _add_zsh_completion_conditions(
    zsh_script: list[str],
    path: list[str],
    nexts: list[str],
    depth: int,
    is_first: bool,
    is_last: bool
):
    # Build the condition string for the current path
    condition = " && ".join([
        f"\"$words[{i + 1}]\" == \"{p}\"" for i, p in enumerate(path)
    ])
    # Construct the if statement based on depth
    control = "if" if is_first else "elif"
    if_statement = f"    {control} [[ {condition} && CURRENT -eq {depth + 1} ]]"
    zsh_script += [
        if_statement,
        "    then",
        f"        subcommands=({' '.join(nexts)})",
    ]
    if is_last:
        zsh_script.append("    fi")
