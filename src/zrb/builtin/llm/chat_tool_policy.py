import os
from zrb.config.config import CFG


def approve_if_path_inside_cwd(args: dict[str, any]) -> bool:
    cwd = os.getcwd()
    return _approve_if_path_inside_parent(args, cwd)


def approve_if_path_inside_journal_dir(args: dict[str, any]) -> bool:
    return _approve_if_path_inside_parent(args, CFG.LLM_JOURNAL_DIR)


def _approve_if_path_inside_parent(args: dict[str, any], parent_path: str) -> bool:
    path = args.get("path")
    paths = args.get("paths")
    if path is not None:
        return _path_inside_parent(str(path), parent_path)
    if paths is not None:
        if isinstance(paths, list):
            return all(_path_inside_parent(str(p), parent_path) for p in paths)
        return False
    return True


def _path_inside_parent(path: str, parent_path: str) -> bool:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        abs_parent_path = os.path.abspath(os.path.expanduser(parent_path))
        return abs_path == abs_parent_path or abs_path.startswith(f"{abs_parent_path}{os.sep}")
    except Exception:
        return False
