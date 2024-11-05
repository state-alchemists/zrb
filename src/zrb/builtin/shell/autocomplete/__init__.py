from ._group import shell_autocomplete_group
from .bash import make_bash_autocomplete
from .subcmd import get_shell_subcommands
from .zsh import make_zsh_autocomplete

assert shell_autocomplete_group
assert make_bash_autocomplete
assert make_zsh_autocomplete
assert get_shell_subcommands
