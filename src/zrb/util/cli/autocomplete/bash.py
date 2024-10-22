from .subcommand import SubCommand


def make_bash_completion_script(cmd: str, subcommands: list[SubCommand]):
    bash_script = [
        "_zrb_complete() {",
        "    local cur subcommands",
        "",
        "    # Get the current word being completed",
        "    cur=\"${COMP_WORDS[COMP_CWORD]}\"  # Current word being completed",
        "",
        "    # Initialize subcommands",
        "    subcommands=\"\"",
        ""
    ]
    # Iterate through command completions to generate conditions
    for index, subcommand in enumerate(subcommands):
        _add_completion_conditions(
            bash_script=bash_script,
            path=subcommand.paths,
            nexts=subcommand.nexts,
            depth=len(subcommand.paths),
            is_first=index == 0,
            is_last=index == (len(subcommands) - 1),
        )
    # Last part
    bash_script += [
        "",
        "    # Generate completion suggestions if subcommands is not empty",
        "    COMPREPLY=( $(compgen -W \"$subcommands\" -- \"$cur\") )",
        "}",
        "# Register the completion function",
        "complete -F _zrb_complete zrb"
    ]
    return "\n".join(bash_script)


def _add_completion_conditions(
    bash_script: list[str],
    path: list[str],
    nexts: list[str],
    depth: int,
    is_first: bool,
    is_last: bool
):
    # Build the condition string for the current path
    condition = " && ".join([
        f"\"${{COMP_WORDS[{i}]}}\" == \"{p}\"" for i, p in enumerate(path)
    ])
    # Construct the if statement based on depth
    control = "if" if is_first else "elif"
    if_statement = f"    {control} [[ $COMP_CWORD -eq {depth} && {condition} ]]"
    bash_script += [
        if_statement,
        "then",
        f"        subcommands=\"{' '.join(nexts)}\"",
    ]
    if is_last:
        bash_script.append("    fi")
