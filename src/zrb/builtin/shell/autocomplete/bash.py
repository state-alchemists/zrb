from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """
_{command_name}_complete() {
    local cur cmd_input subcmd_output cache_file
    local -a subcommands

    cur="${COMP_WORDS[COMP_CWORD]}"
    cmd_input="{command_name} shell autocomplete subcmd ${COMP_WORDS[@]:0:$COMP_CWORD}"

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

    IFS=' ' read -r -a subcommands <<< "$subcmd_output"
    COMPREPLY=( $(compgen -W "${subcommands[*]}" -- "$cur") )
}

complete -F _{command_name}_complete {command_name}

"""


@make_task(
    name="make-bash-autocomplete",
    description="🐚 Create Zrb autocomplete script for bash",
    group=shell_autocomplete_group,
    alias="bash",
)
def make_bash_autocomplete(ctx: AnyContext):
    return _COMPLETION_SCRIPT.replace("{command_name}", CFG.ROOT_GROUP_NAME)
