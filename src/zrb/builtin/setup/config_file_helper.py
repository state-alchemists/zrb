import os

from zrb.util.file import read_file, write_file


def append_config_block_if_missing(file_path: str, config_block: str) -> bool:
    """Append `config_block` to `file_path` unless it's already present.

    Creates the file first if it doesn't exist. Used by shell/tool setup
    tasks (asdf, tmux, zsh) that append a sourcing line to a user's rc/config
    file without duplicating it on repeated runs.

    Returns True if the block was appended, False if it was already present.
    """
    if not os.path.isfile(file_path):
        write_file(file_path, "")
    content = read_file(file_path)
    if config_block in content:
        return False
    write_file(file_path, [content, config_block, ""])
    return True
