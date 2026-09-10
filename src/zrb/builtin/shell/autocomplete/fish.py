from zrb.builtin.group import shell_autocomplete_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task

_COMPLETION_SCRIPT = """
function __{command_name}_complete
    # `commandline -opc` returns the tokens before the cursor, excluding the
    # word currently being typed (fish filters candidates against that word
    # on its own, unlike bash/zsh which need it passed to compgen/_describe).
    set -l cmd_input (commandline -opc)

    # Cache the subcommand list for a minute, keyed by cwd + the command
    # being completed, so repeated Tab presses don't pay a fresh process
    # spawn (and zrb_init.py reload) on every keystroke. Lives under the
    # user's own cache dir (not shared /tmp) -- a world-writable directory
    # with a filename any local user can predict lets another user pre-plant
    # a symlink there and hijack the write.
    set -l cache_dir $XDG_CACHE_HOME
    if test -z "$cache_dir"
        set cache_dir "$HOME/.cache"
    end
    set cache_dir "$cache_dir/{command_name}"
    mkdir -p "$cache_dir" 2>/dev/null
    chmod 700 "$cache_dir" 2>/dev/null
    set -l cache_file "$cache_dir/autocomplete-cache-"(printf '%s' "$PWD $cmd_input" | tr -c '[:alnum:]' '_')
    set -l fresh (find "$cache_file" -mmin -1 2>/dev/null)
    if test -n "$fresh"
        cat "$cache_file"
        return
    end

    set -l subcommands (string split ' ' -- ({command_name} shell autocomplete subcmd $cmd_input 2>/dev/null))
    printf '%s\\n' $subcommands | tee "$cache_file"
end

complete -c {command_name} -f -a '(__{command_name}_complete)'
"""


@make_task(
    name="make-fish-autocomplete",
    description="🐟 Create Zrb autocomplete script for fish",
    group=shell_autocomplete_group,
    alias="fish",
)
def make_fish_autocomplete(ctx: AnyContext):
    return _COMPLETION_SCRIPT.replace("{command_name}", CFG.ROOT_GROUP_NAME)
