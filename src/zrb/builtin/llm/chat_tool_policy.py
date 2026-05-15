import os
from typing import Any

from zrb.config.config import CFG


def approve_if_path_inside_cwd(args: dict[str, Any]) -> bool:
    cwd = os.getcwd()
    return _approve_if_path_inside_parent(args, cwd)


def approve_if_path_inside_journal_dir(args: dict[str, Any]) -> bool:
    return _approve_if_path_inside_parent(args, CFG.LLM_JOURNAL_DIR)


def approve_if_mv_inside_journal_dir(args: dict[str, Any]) -> bool:
    journal_dir = CFG.LLM_JOURNAL_DIR
    src = args.get("src")
    dst = args.get("dst")
    if src is None or dst is None:
        return False
    return _path_inside_parent(str(src), journal_dir) and _path_inside_parent(
        str(dst), journal_dir
    )


def _approve_if_path_inside_parent(args: dict[str, Any], parent_path: str) -> bool:
    path = args.get("path")
    if path is not None:
        return _path_inside_parent(str(path), parent_path)
    return True


def _path_inside_parent(path: str, parent_path: str) -> bool:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        abs_parent_path = os.path.abspath(os.path.expanduser(parent_path))
        return abs_path == abs_parent_path or abs_path.startswith(
            f"{abs_parent_path}{os.sep}"
        )
    except Exception:
        return False
