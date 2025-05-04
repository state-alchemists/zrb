from zrb.builtin.base64 import decode_base64, encode_base64, validate_base64
from zrb.builtin.git import (
    get_git_diff,
    git_commit,
    git_pull,
    git_push,
    prune_local_branches,
)
from zrb.builtin.git_subtree import git_add_subtree, git_pull_subtree, git_push_subtree
from zrb.builtin.http import generate_curl, http_request
from zrb.builtin.jwt import decode_jwt, encode_jwt, validate_jwt
from zrb.builtin.llm.llm_chat import llm_chat
from zrb.builtin.md5 import hash_md5, sum_md5, validate_md5
from zrb.builtin.project.add.fastapp.fastapp_task import add_fastapp_to_project
from zrb.builtin.project.create.project_task import create_project
from zrb.builtin.python import format_python_code
from zrb.builtin.random import shuffle_values, throw_dice
from zrb.builtin.setup.asdf.asdf import setup_asdf
from zrb.builtin.setup.latex.ubuntu import setup_latex_on_ubuntu
from zrb.builtin.setup.tmux.tmux import setup_tmux
from zrb.builtin.setup.ubuntu import setup_ubuntu
from zrb.builtin.setup.zsh.zsh import setup_zsh
from zrb.builtin.shell.autocomplete.bash import make_bash_autocomplete
from zrb.builtin.shell.autocomplete.subcmd import get_shell_subcommands
from zrb.builtin.shell.autocomplete.zsh import make_zsh_autocomplete
from zrb.builtin.todo import (
    add_todo,
    archive_todo,
    complete_todo,
    edit_todo,
    list_todo,
    log_todo,
    show_todo,
)
from zrb.builtin.uuid import (
    generate_uuid_v1,
    generate_uuid_v3,
    generate_uuid_v4,
    generate_uuid_v5,
    validate_uuid,
    validate_uuid_v1,
    validate_uuid_v3,
    validate_uuid_v4,
    validate_uuid_v5,
)

assert create_project
assert add_fastapp_to_project
assert get_shell_subcommands
assert make_bash_autocomplete
assert make_zsh_autocomplete
assert encode_base64
assert decode_base64
assert validate_base64
assert encode_jwt
assert decode_jwt
assert validate_jwt
assert llm_chat
assert hash_md5
assert sum_md5
assert validate_md5
assert get_git_diff
assert prune_local_branches
assert format_python_code
assert git_commit
assert git_pull
assert git_push
assert git_add_subtree
assert git_pull_subtree
assert git_push_subtree
assert list_todo
assert add_todo
assert archive_todo
assert edit_todo
assert complete_todo
assert log_todo
assert show_todo
assert throw_dice
assert shuffle_values
assert setup_ubuntu
assert setup_latex_on_ubuntu
assert setup_asdf
assert setup_tmux
assert setup_zsh
assert validate_uuid
assert validate_uuid_v1
assert validate_uuid_v3
assert validate_uuid_v4
assert validate_uuid_v5
assert generate_uuid_v1
assert generate_uuid_v3
assert generate_uuid_v4
assert generate_uuid_v5
assert http_request
assert generate_curl
