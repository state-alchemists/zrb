from zrb.builtin.base64 import decode_base64, encode_base64
from zrb.builtin.git.diff import get_git_diff
from zrb.builtin.md5 import hash_md5, sum_md5
from zrb.builtin.project.add.fastapp import add_fastapp_to_project
from zrb.builtin.project.create.create import create_project
from zrb.builtin.shell.autocomplete.bash import make_bash_autocomplete
from zrb.builtin.shell.autocomplete.subcmd import get_shell_subcommands
from zrb.builtin.shell.autocomplete.zsh import make_zsh_autocomplete

assert create_project
assert add_fastapp_to_project
assert get_shell_subcommands
assert make_bash_autocomplete
assert make_zsh_autocomplete
assert encode_base64
assert decode_base64
assert hash_md5
assert sum_md5
assert get_git_diff
