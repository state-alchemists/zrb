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


def _path_inside_any_parent(path: str, parent_paths: list[str]) -> bool:
    """Check if *path* is inside any of the given *parent_paths*."""
    for parent in parent_paths:
        if _path_inside_parent(path, parent):
            return True
    return False


def approve_if_path_inside_skill_or_plugin_dir(args: dict[str, Any]) -> bool:
    """Auto-approve when *path* is inside a discovered skill or plugin directory."""
    path = args.get("path")
    if path is None:
        return True
    # lazy: skill_manager transitively pulls CFG and other modules; not needed
    # at module load time.
    from zrb.llm.skill.manager import skill_manager

    abs_path = os.path.abspath(os.path.expanduser(str(path)))
    # 1. Check resolved skill search directories (builtin + home + project + extras)
    for search_dir in skill_manager.get_search_directories():
        if _path_inside_parent(abs_path, str(search_dir)):
            return True
    # 2. Check explicit plugin directories (both env-var and programmatically set)
    if _path_inside_any_parent(abs_path, list(CFG.LLM_PLUGIN_DIRS)):
        return True
    return False
