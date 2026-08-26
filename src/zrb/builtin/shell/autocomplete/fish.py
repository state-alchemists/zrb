from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """
# Fish dynamic completion script
function __{command_name}_complete
    # `commandline -opc` returns the tokens before the cursor, excluding the
    # word currently being typed (fish filters candidates against that word
    # on its own, unlike bash/zsh which need it passed to compgen/_describe).
    set -l cmd_input (commandline -opc)

    set -l tmp_dir $TMPDIR
    if test -z "$tmp_dir"
        set tmp_dir /tmp
    end
    set -l cache_file "$tmp_dir/.{command_name}-autocomplete-cache-"(printf '%s' "$PWD $cmd_input" | tr -c '[:alnum:]' '_')

    # Cache the subcommand list for a minute, keyed by cwd + the command
    # being completed, so repeated Tab presses don't pay a fresh process
    # spawn (and zrb_init.py reload) on every keystroke.
    set -l fresh (find "$cache_file" -mmin -1 2>/dev/null)
    if test -n "$fresh"
        cat "$cache_file"
        return
    end

    set -l subcommands (string split ' ' -- ({command_name} shell autocomplete subcmd $cmd_input 2>/dev/null))
    printf '%s\\n' $subcommands | tee "$cache_file"
end

# Register the completion function for {command_name}
complete -c {command_name} -f -a '(__{command_name}_complete)'
"""


@make_task(
    name="make-fish-autocomplete",
    description="🐚 Create Zrb autocomplete script for fish",
    group=shell_autocomplete_group,
    alias="fish",
)
def make_fish_autocomplete(ctx: AnyContext):
    return _COMPLETION_SCRIPT.replace("{command_name}", CFG.ROOT_GROUP_NAME)
