from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """
# Zsh dynamic completion script
_{command_name}_complete() {
    local -a subcommands
    local cmd_input
    local subcmd_output
    local cache_file

    cmd_input="{command_name} shell autocomplete subcmd ${words[1,CURRENT-1]}"

    # Cache the subcommand list for a minute, keyed by cwd + the command
    # being completed, so repeated Tab presses don't pay a fresh process
    # spawn (and zrb_init.py reload) on every keystroke.
    cache_file="${TMPDIR:-/tmp}/.{command_name}-autocomplete-cache-$(printf '%s' "$PWD $cmd_input" | tr -c '[:alnum:]' '_')"

    if [ -n "$(find "$cache_file" -mmin -1 2>/dev/null)" ]; then
        subcmd_output=$(cat "$cache_file")
    else
        subcmd_output=$(eval "$cmd_input 2>/dev/null")
        printf '%s' "$subcmd_output" > "$cache_file"
    fi

    # Split the output into an array using spaces or newlines as separators
    subcommands=(${=subcmd_output})

    # Provide the completion suggestions
    _describe 'subcommand' subcommands
}

# Register the completion function
compdef _{command_name}_complete {command_name}
"""


@make_task(
    name="make-zsh-autocomplete",
    description="🐚 Create Zrb autocomplete script for zsh",
    group=shell_autocomplete_group,
    alias="zsh",
)
def make_zsh_autocomplete(ctx: AnyContext):
    return _COMPLETION_SCRIPT.replace("{command_name}", CFG.ROOT_GROUP_NAME)
