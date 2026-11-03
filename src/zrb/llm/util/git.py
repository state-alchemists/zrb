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
            cwd=cwd,
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

    A common directory whose name is not `.git` is the repository itself, not a
    container of it: a submodule's lives at `<super>/.git/modules/<name>`, and
    its parent's basename is `modules` — the name of a directory that says
    nothing about which repository is in hand.

    The flag that would print that path absolute, `--path-format=absolute`, needs
    Git 2.31 and answers nothing on anything older — and an empty answer reads as
    "outside any checkout", which silently turns the journal's scoping off. The
    plain command answers the same thing on every version, relative to the
    directory it ran in, so the resolution happens here instead.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
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
    return repository_root_from_common_dir(_absolute(res.stdout.strip(), cwd))


def _absolute(path: str, cwd: str) -> str:
    """*path* as git printed it, resolved against the directory git ran in.

    `rev-parse --git-common-dir` answers `.git` at a repository's top,
    `../../.git` from a subdirectory, and an absolute path for a linked
    worktree; `os.path.join` keeps an absolute path as it is."""
    if not path:
        return ""
    return os.path.abspath(os.path.join(cwd, path))


def repository_root_from_common_dir(common_dir: str) -> str:
    """The repository's top-level for one `--git-common-dir` answer.

    Split out because the shape of that answer is the whole rule: a directory
    named `.git` is the repository's container, and anything else *is* the
    repository — a submodule's lives at `<super>/.git/modules/<name>`."""
    if not common_dir:
        return ""
    if os.path.basename(common_dir) == ".git":
        return os.path.dirname(common_dir)
    return common_dir


def repository_name(cwd: str) -> str:
    """The repository's directory name at *cwd*, or ``""`` outside one."""
    root = repository_root(cwd)
    return os.path.basename(root) if root else ""
