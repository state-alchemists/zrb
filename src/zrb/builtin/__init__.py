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
from zrb.builtin.llm.llm_ask import llm_ask
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
