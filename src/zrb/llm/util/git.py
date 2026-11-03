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
    "outside any checkout". The plain command answers the same thing on every
    version, relative to the directory it ran in, so the resolution happens here
    instead.

    `--is-inside-work-tree` is asked in the same call: a bare repository has a
    common directory but no checkout, and a session poking at one is outside any
    work tree.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree", "--git-common-dir"],
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
    inside, _, common = res.stdout.partition("\n")
    if inside.strip() != "true":
        return ""
    return repository_root_from_common_dir(_absolute(common.strip(), cwd))


def checkout_root(cwd: str) -> str:
    """The top-level directory of the work tree containing *cwd*, or ``""``.

    This is the tree a path is relative to, which is a different question from
    the one `repository_root` answers: that one resolves the common directory,
    so every worktree of one repository gets one name — and a linked worktree
    then points at the main checkout. Reading a file relative to that answer
    reads the wrong tree, and a submodule, whose common directory is
    `<super>/.git/modules/<name>`, has no work tree there at all.

    `--show-toplevel` names the tree the caller stands in, worktree or
    submodule. It answers nothing in a bare repository, which has none.

    Deliberately not cached, unlike `repository_root`: a checkout can be
    removed and re-cloned at the same path while a session is open, and a name
    that stayed the same would be a cached *tree* that is now somebody else's —
    the one case where reading a digest there means a note expires on evidence
    it never had. One probe per compose is the price.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
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
    root = res.stdout.strip()
    # Realpath, so a symlinked way of naming the same checkout is one tree: the
    # checkout id recorded beside a digest is taken from this answer.
    return os.path.realpath(root) if root else ""


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
