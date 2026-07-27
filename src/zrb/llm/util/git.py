import os
import subprocess
from functools import lru_cache

from zrb.config.config import CFG


@lru_cache(maxsize=8)
def _check_git_dir(cwd: str) -> bool:
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
    except Exception:
        return False


def is_inside_git_dir() -> bool:
    return _check_git_dir(os.getcwd())
