from .data import CommandCompletion


def generate_bash_autocompletion(cmd: str, command_completions: CommandCompletion):
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
    for index, completion in enumerate(command_completions):
        _add_completion_conditions(
            bash_script=bash_script,
            path=completion.paths,
            subcommands=completion.subcommands,
            depth=len(completion.paths),
            is_first=index == 0,
            is_last=index == (len(command_completions) - 1),
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
    subcommands: list[str],
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
        f"        subcommands=\"{' '.join(subcommands)}\"",
    ]
    if is_last:
        bash_script.append("    fi")
