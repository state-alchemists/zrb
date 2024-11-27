from zrb.builtin.base64 import decode_base64, encode_base64
from zrb.builtin.git import (
    get_git_diff,
    git_commit,
    git_pull,
    git_push,
    prune_local_branches,
)
from zrb.builtin.git_subtree import git_add_subtree, git_pull_subtree, git_push_subtree
from zrb.builtin.llm.llm_chat import llm_chat
from zrb.builtin.md5 import hash_md5, sum_md5
from zrb.builtin.project.add.fastapp import add_fastapp_to_project
from zrb.builtin.project.create.create import create_project
from zrb.builtin.python import format_python_code
from zrb.builtin.shell.autocomplete.bash import make_bash_autocomplete
from zrb.builtin.shell.autocomplete.subcmd import get_shell_subcommands
from zrb.builtin.shell.autocomplete.zsh import make_zsh_autocomplete
from zrb.builtin.todo import todo_add, todo_complete, todo_edit, todo_list, todo_log

assert create_project
assert add_fastapp_to_project
assert get_shell_subcommands
assert make_bash_autocomplete
assert make_zsh_autocomplete
assert encode_base64
assert decode_base64
assert llm_chat
assert hash_md5
assert sum_md5
assert get_git_diff
assert prune_local_branches
assert format_python_code
assert git_commit
assert git_pull
assert git_push
assert git_add_subtree
assert git_pull_subtree
assert git_push_subtree
assert todo_list
assert todo_add
assert todo_edit
assert todo_complete
assert todo_log
