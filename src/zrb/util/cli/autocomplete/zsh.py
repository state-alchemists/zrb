from .data import CommandCompletion


def generate_zsh_autocompletion(cmd: str, command_completions: CommandCompletion):
    zsh_script = [
        "_zrb_complete() {",
        "    local -a subcommands",
        "",
        "    # Initialize subcommands",
        "    subcommands=()",
        ""
    ]
    # Iterate through command completions to generate conditions
    for index, completion in enumerate(command_completions):
        _add_zsh_completion_conditions(
            zsh_script=zsh_script,
            path=completion.paths,
            subcommands=completion.subcommands,
            depth=len(completion.paths),
            is_first=index == 0,
            is_last=index == (len(command_completions) - 1),
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
    subcommands: list[str],
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
        f"        subcommands=({' '.join(subcommands)})",
    ]
    if is_last:
        zsh_script.append("    fi")
