from zrb.builtin.base64 import decode_base64, encode_base64, validate_base64
from zrb.builtin.case import convert_case, slugify
from zrb.builtin.config import explain_config
from zrb.builtin.cron import parse_cron
from zrb.builtin.datetime import epoch_to_iso, iso_to_epoch, now
from zrb.builtin.git import (
    get_git_diff,
    git_commit,
    git_pull,
    git_push,
    prune_local_branches,
)
from zrb.builtin.git_subtree import git_add_subtree, git_pull_subtree, git_push_subtree
from zrb.builtin.hash import hash_file, hash_hmac, hash_text
from zrb.builtin.hex import decode_hex, dump_hex, encode_hex
from zrb.builtin.http import generate_curl, http_request
from zrb.builtin.json import (
    format_json,
    get_json,
    json_to_yaml,
    minify_json,
    validate_json,
    yaml_to_json,
)
from zrb.builtin.jwt import decode_jwt, encode_jwt, validate_jwt
from zrb.builtin.llm.chat import llm_chat
from zrb.builtin.md5 import hash_md5, sum_md5, validate_md5
from zrb.builtin.number import convert_base
from zrb.builtin.python import format_python_code
from zrb.builtin.random import (
    generate_password,
    generate_string,
    generate_token,
    shuffle_values,
    throw_dice,
)
from zrb.builtin.searxng.start import start_searxng
from zrb.builtin.setup.asdf.asdf import setup_asdf
from zrb.builtin.setup.latex.ubuntu import setup_latex_on_ubuntu
from zrb.builtin.setup.tmux.tmux import setup_tmux
from zrb.builtin.setup.ubuntu import setup_ubuntu
from zrb.builtin.setup.zsh.zsh import setup_zsh
from zrb.builtin.shell.autocomplete.bash import make_bash_autocomplete
from zrb.builtin.shell.autocomplete.powershell import make_powershell_autocomplete
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
from zrb.builtin.ulid import generate_ulid, validate_ulid
from zrb.builtin.url import decode_url, encode_url, parse_url
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

__all__ = [
    "explain_config",
    "decode_base64",
    "encode_base64",
    "validate_base64",
    "convert_case",
    "slugify",
    "parse_cron",
    "epoch_to_iso",
    "iso_to_epoch",
    "now",
    "get_git_diff",
    "git_commit",
    "git_pull",
    "git_push",
    "prune_local_branches",
    "git_add_subtree",
    "git_pull_subtree",
    "git_push_subtree",
    "hash_file",
    "hash_hmac",
    "hash_text",
    "decode_hex",
    "dump_hex",
    "encode_hex",
    "generate_curl",
    "http_request",
    "format_json",
    "get_json",
    "json_to_yaml",
    "minify_json",
    "validate_json",
    "yaml_to_json",
    "decode_jwt",
    "encode_jwt",
    "validate_jwt",
    "llm_chat",
    "hash_md5",
    "sum_md5",
    "validate_md5",
    "convert_base",
    "format_python_code",
    "generate_password",
    "generate_string",
    "generate_token",
    "shuffle_values",
    "throw_dice",
    "start_searxng",
    "setup_asdf",
    "setup_latex_on_ubuntu",
    "setup_tmux",
    "setup_ubuntu",
    "setup_zsh",
    "make_bash_autocomplete",
    "make_powershell_autocomplete",
    "get_shell_subcommands",
    "make_zsh_autocomplete",
    "add_todo",
    "archive_todo",
    "complete_todo",
    "edit_todo",
    "list_todo",
    "log_todo",
    "show_todo",
    "generate_ulid",
    "validate_ulid",
    "decode_url",
    "encode_url",
    "parse_url",
    "generate_uuid_v1",
    "generate_uuid_v3",
    "generate_uuid_v4",
    "generate_uuid_v5",
    "validate_uuid",
    "validate_uuid_v1",
    "validate_uuid_v3",
    "validate_uuid_v4",
    "validate_uuid_v5",
]
