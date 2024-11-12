from zrb.builtin.group import shell_autocomplete_group
from zrb.context.context import Context
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """
# Zsh dynamic completion script
_zrb_complete() {
    local -a subcommands
    local cmd_input
    local subcmd_output

    # Build the command input based on the current words
    cmd_input="zrb shell autocomplete subcmd ${words[1,CURRENT-1]}"

    # Fetch the subcommands dynamically and store them in a variable
    subcmd_output=$(eval "$cmd_input 2>/dev/null")

    # Split the output into an array using spaces or newlines as separators
    subcommands=(${=subcmd_output})

    # Provide the completion suggestions
    _describe 'subcommand' subcommands
}

# Register the completion function
compdef _zrb_complete zrb
"""


@make_task(
    name="make-zsh-autocomplete",
    description="Create Zrb autocomplete script for zsh",
    group=shell_autocomplete_group,
    alias="zsh",
)
def make_zsh_autocomplete(ctx: Context):
    return _COMPLETION_SCRIPT
