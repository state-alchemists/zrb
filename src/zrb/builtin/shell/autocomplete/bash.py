from zrb.builtin.group import shell_autocomplete_group
from zrb.context.context import Context
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """
# Bash dynamic completion script
_zrb_complete() {
    local cur cmd_input subcmd_output
    local -a subcommands

    # Get the current word being completed
    cur="${COMP_WORDS[COMP_CWORD]}"

    # Build the command input dynamically (excluding the current word being typed)
    cmd_input="zrb shell autocomplete subcmd ${COMP_WORDS[@]:0:$COMP_CWORD}"

    # Fetch the subcommands dynamically
    subcmd_output=$(eval "$cmd_input 2>/dev/null")

    # Split the output into an array of subcommands using whitespace
    IFS=' ' read -r -a subcommands <<< "$subcmd_output"

    # Generate completion suggestions if subcommands is not empty
    COMPREPLY=( $(compgen -W "${subcommands[*]}" -- "$cur") )
}

# Register the completion function for zrb
complete -F _zrb_complete zrb

"""


@make_task(
    name="make-bash-autocomplete",
    description="Create Zrb autocomplete script for bash",
    group=shell_autocomplete_group,
    alias="bash",
)
def make_bash_autocomplete(ctx: Context):
    return _COMPLETION_SCRIPT
