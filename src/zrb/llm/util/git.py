import os
import subprocess
from functools import lru_cache

from zrb.config.config import CFG


@lru_cache(maxsize=8)
def check_git_dir(cwd: str) -> bool:
    """Cached probe. Raises ``TimeoutExpired`` rather than answering False.

    A timeout is transient; ``lru_cache`` does not memoize a raised exception,
    so re-raising keeps it from sticking as "not a git dir".
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            # A blocked git (credential prompt, index.lock) would stall every
            # prompt compose.
            timeout=CFG.LLM_GIT_CMD_TIMEOUT / 1000,
        )
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        raise
    except Exception:
        return False


def is_inside_git_dir() -> bool:
    try:
        return check_git_dir(os.getcwd())
    except subprocess.TimeoutExpired:
        return False


@lru_cache(maxsize=8)
def repository_root(cwd: str) -> str:
    """The top-level directory of the repository containing *cwd*, or ``""``.

    ``--git-common-dir`` rather than ``--show-toplevel``: a worktree's own
    top-level is the worktree directory, whose name is a branch, and every
    worktree of one repository has to answer with the same name.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=CFG.LLM_GIT_CMD_TIMEOUT / 1000,
        )
    except subprocess.TimeoutExpired:
        return ""
    except OSError:
        return ""
    if res.returncode != 0:
        return ""
    common_dir = res.stdout.strip()
    if not common_dir:
        return ""
    return os.path.dirname(common_dir)


def repository_name(cwd: str) -> str:
    """The repository's directory name at *cwd*, or ``""`` outside one."""
    root = repository_root(cwd)
    return os.path.basename(root) if root else ""
