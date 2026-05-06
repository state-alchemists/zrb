import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize=8)
def _check_git_dir(cwd: str) -> bool:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0
    except Exception:
        return False


def is_inside_git_dir() -> bool:
    return _check_git_dir(os.getcwd())
