import asyncio
import os
from contextvars import ContextVar
from datetime import datetime

from zrb.llm.tool.wrapper import tool_safe_async

active_worktree: ContextVar[str] = ContextVar("zrb_active_worktree", default="")


@tool_safe_async
async def enter_worktree(branch_name: str = "", cwd: str = "") -> str:
    """
    Creates an isolated git worktree on a new branch. Returns the path to the worktree directory.

    Use for risky experiments, parallel approaches, or staging changes before merging.
    Use `keep_branch=True` in `ExitWorktree` to preserve the branch for later merging.
    Use `cwd` to specify the repository root if the current directory is not the target repo.
    After creation: pass the worktree path as `cwd` to `Bash`; use absolute paths with `Read`, `Write`, `Edit`, and `Grep` (they don't accept `cwd`).
    """
    from zrb.config.config import CFG

    cwd = cwd or os.getcwd()

    root_proc = await asyncio.create_subprocess_exec(
        "git",
        "rev-parse",
        "--show-toplevel",
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    root_out, err = await root_proc.communicate()
    if root_proc.returncode != 0:
        return (
            f"Error: Not inside a git repository.\n"
            f"[SYSTEM SUGGESTION]: Navigate to a directory that is a git repository root, "
            f"or provide cwd pointing to one."
        )

    git_root = root_out.decode().strip()

    if not branch_name:
        branch_name = f"worktree-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    worktree_dir = os.path.join(git_root, f".{CFG.ROOT_GROUP_NAME}", "worktree")
    os.makedirs(worktree_dir, exist_ok=True)
    worktree_path = os.path.join(worktree_dir, branch_name)

    proc = await asyncio.create_subprocess_exec(
        "git",
        "worktree",
        "add",
        "-b",
        branch_name,
        worktree_path,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_msg = stderr.decode().strip()
        if "already exists" in err_msg.lower():
            return (
                f"Error: Worktree or branch '{branch_name}' already exists.\n"
                f"[SYSTEM SUGGESTION]: Use a different branch_name or list existing worktrees with ListWorktrees."
            )
        return (
            f"Error: Failed to create worktree: {err_msg}\n"
            f"[SYSTEM SUGGESTION]: Check if the branch name is valid and if you have permissions."
        )

    active_worktree.set(worktree_path)
    _ensure_gitignore(git_root, f".{CFG.ROOT_GROUP_NAME}/worktree/")
    return (
        f"Worktree created: {worktree_path}\n"
        f"Branch: {branch_name}\n"
        f"Use this path as cwd for Bash commands targeting this worktree."
    )


@tool_safe_async
async def exit_worktree(worktree_path: str, keep_branch: bool = False) -> str:
    """
    Removes a git worktree created with `EnterWorktree`.

    Use `keep_branch=True` to preserve the branch for merging; default deletes it along with all its commits.
    Always clean up worktrees after use.
    """
    cwd = os.getcwd()

    if not os.path.isdir(worktree_path):
        return (
            f"Error: Worktree path does not exist: {worktree_path}\n"
            f"[SYSTEM SUGGESTION]: Use ListWorktrees to see active worktrees and their exact paths."
        )

    branch_proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        worktree_path,
        "rev-parse",
        "--abbrev-ref",
        "HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    branch_out, _ = await branch_proc.communicate()
    branch_name = branch_out.decode().strip() if branch_proc.returncode == 0 else None

    rm_proc = await asyncio.create_subprocess_exec(
        "git",
        "worktree",
        "remove",
        "--force",
        worktree_path,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, rm_err = await rm_proc.communicate()
    if rm_proc.returncode != 0:
        return (
            f"Error: Failed to remove worktree: {rm_err.decode().strip()}\n"
            f"[SYSTEM SUGGESTION]: Ensure no uncommitted changes are in the worktree, "
            f"then retry. Use ListWorktrees to check status."
        )

    active_worktree.set("")
    lines = [f"Worktree removed: {worktree_path}"]

    if branch_name and not keep_branch:
        del_proc = await asyncio.create_subprocess_exec(
            "git",
            "branch",
            "-D",
            branch_name,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, del_err = await del_proc.communicate()
        if del_proc.returncode == 0:
            lines.append(f"Branch deleted: {branch_name}")
        else:
            lines.append(
                f"Branch kept: {branch_name} (could not delete — {del_err.decode().strip()})"
            )
    elif branch_name:
        lines.append(f"Branch kept: {branch_name}")

    return "\n".join(lines)


@tool_safe_async
async def list_worktrees() -> str:
    """
    Lists all active git worktrees for the current repository (path, branch, commit).
    """
    cwd = os.getcwd()

    proc = await asyncio.create_subprocess_exec(
        "git",
        "worktree",
        "list",
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return (
            f"Error: Not inside a git repository.\n"
            f"[SYSTEM SUGGESTION]: Navigate to a git repository root."
        )

    output = stdout.decode().strip()
    return output if output else "No worktrees found (only the main working tree)."


def _ensure_gitignore(git_root: str, pattern: str) -> None:
    """Add pattern to {git_root}/.gitignore if not already present."""
    gitignore_path = os.path.join(git_root, ".gitignore")
    try:
        if os.path.exists(gitignore_path):
            content = open(gitignore_path, "r", encoding="utf-8").read()
            lines = content.splitlines()
            if any(line.strip() == pattern for line in lines):
                return
            with open(gitignore_path, "a", encoding="utf-8") as f:
                prefix = "\n" if content and not content.endswith("\n") else ""
                f.write(f"{prefix}{pattern}\n")
        else:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(f"{pattern}\n")
    except OSError:
        pass


# Set function names to PascalCase for tool display
enter_worktree.__name__ = "EnterWorktree"
exit_worktree.__name__ = "ExitWorktree"
list_worktrees.__name__ = "ListWorktrees"
