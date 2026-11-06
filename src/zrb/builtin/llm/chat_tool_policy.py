import os
from typing import Any

from zrb.config.config import CFG
from zrb.llm.ambient_state import get_active_worktree


def approve_if_path_inside_cwd(args: dict[str, Any]) -> bool:
    cwd = os.getcwd()
    return approve_if_path_inside_parent(args, cwd)


def is_path_inside_active_worktree(args: dict[str, object]) -> bool:
    """Whether *path* is inside the worktree the session is working on.

    ``EnterWorktree`` puts the tree outside the checkout, so a session that
    moved into one read every file there through an approval prompt. A call
    that names no path is left to the working-directory rules: `LS`, `Glob` and
    `Grep` default to `"."`, and approving a pathless call here would approve
    all of them — including the ones meant for the process's own directory.
    """
    worktree = get_active_worktree()
    path = args.get("path")
    if not worktree or not isinstance(path, str) or not path:
        return False
    return path_inside_parent(path, worktree)


def approve_if_path_inside_notes_dir(args: dict[str, Any]) -> bool:
    return approve_if_path_inside_parent(args, CFG.LLM_NOTES_DIR)


def is_path_inside_notes_outside_memory(args: dict[str, object]) -> bool:
    """The notes directory, minus the memory store that now lives inside it.

    Memory has its own tools, and they enforce what a raw file write does not: a
    kebab-case id, a bounded claim, no prompt-injection marker, and the core's
    cap. `Write` on `core.md` or a fact file is the same act with none of those
    checks, and `RM` deletes a claim `Forget` would have retired — so mutating
    the store asks. Reading it stays approved: the store is still notes.
    """
    if not approve_if_path_inside_notes_dir(args):
        return False
    path = args.get("path")
    return path is None or not path_inside_parent(str(path), CFG.LLM_MEMORY_DIR)


def approve_if_mv_inside_notes_dir(args: dict[str, Any]) -> bool:
    """Both ends inside the notes directory, neither of them in the store."""
    src = args.get("src")
    dst = args.get("dst")
    if src is None or dst is None:
        return False
    ends = (str(src), str(dst))
    if not all(path_inside_parent(end, CFG.LLM_NOTES_DIR) for end in ends):
        return False
    return not any(path_inside_parent(end, CFG.LLM_MEMORY_DIR) for end in ends)


def approve_if_path_inside_parent(args: dict[str, Any], parent_path: str) -> bool:
    path = args.get("path")
    if path is not None:
        return path_inside_parent(str(path), parent_path)
    return True


def path_inside_parent(path: str, parent_path: str) -> bool:
    """Whether *path* is *parent_path* or sits below it, symlinks resolved.

    Resolved, because otherwise the answer is about the string: a symlink in the
    notes directory called `memory-link` would read as an ordinary note while the
    write lands in the store, and one in the working directory would read as a
    project file while the read lands outside it. Approval is about the file that
    is actually touched.
    """
    try:
        abs_path = _resolved(path)
        abs_parent_path = _resolved(parent_path)
        return abs_path == abs_parent_path or abs_path.startswith(
            f"{abs_parent_path}{os.sep}"
        )
    except Exception:
        return False


def _resolved(path: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def path_inside_any_parent(path: str, parent_paths: list[str]) -> bool:
    """Check if *path* is inside any of the given *parent_paths*."""
    for parent in parent_paths:
        if path_inside_parent(path, parent):
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
    # Resolved skill search directories (builtin + home + project + extras)
    for search_dir in skill_manager.search_dirs:
        if path_inside_parent(abs_path, str(search_dir)):
            return True
    # Explicit plugin directories (both env-var and programmatically set)
    if path_inside_any_parent(abs_path, list(CFG.LLM_PLUGIN_DIRS)):
        return True
    return False
