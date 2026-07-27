import os
import subprocess
from functools import lru_cache

from zrb.config.config import CFG


@lru_cache(maxsize=8)
def _check_git_dir(cwd: str) -> bool:
    """Cached probe. Raises ``TimeoutExpired`` rather than answering False.

    A timeout is a *transient* condition, unlike a missing git or a non-repo
    directory, so it must not be memoized: one cold-cache stall would otherwise
    stick as "not a git dir" for the rest of the process, silently disabling the
    live-context git block and the worktree tools. ``lru_cache`` does not
    memoize a raised exception, so letting it escape is what keeps the next call
    retrying — ``is_inside_git_dir`` converts it to the same safe False.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            # Bounded: this gates the live-context git block and the worktree
            # tools, and it ran unbounded — a git that blocks (credential prompt,
            # index.lock contention, unreachable remote in a gitdir file) stalled
            # every prompt compose behind it. A timeout reads as "not a git dir",
            # which is the same safe answer the except branch already gives.
            timeout=CFG.LLM_GIT_CMD_TIMEOUT / 1000,
        )
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        raise
    except Exception:
        return False


def is_inside_git_dir() -> bool:
    try:
        return _check_git_dir(os.getcwd())
    except subprocess.TimeoutExpired:
        return False
