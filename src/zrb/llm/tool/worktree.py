import asyncio
import os
from datetime import datetime


async def enter_worktree(branch_name: str = "") -> str:
    """
    Creates an isolated git worktree on a new branch. Returns the path to the worktree directory.

    Use for risky experiments, parallel approaches, or staging changes before merging.
    Use `keep_branch=True` in `ExitWorktree` to preserve the branch for later merging.
    """
    cwd = os.getcwd()

    # Verify we're inside a git repo
    check = await asyncio.create_subprocess_exec(
        "git",
        "rev-parse",
        "--git-dir",
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await check.communicate()
    if check.returncode != 0:
        raise RuntimeError(f"Not inside a git repository: {err.decode().strip()}")

    if not branch_name:
        branch_name = f"worktree-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Place the worktree in the system temp directory
    import tempfile

    worktree_path = os.path.join(tempfile.gettempdir(), f"zrb-{branch_name}")

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
        raise RuntimeError(f"Failed to create worktree: {stderr.decode().strip()}")

    return (
        f"Worktree created at: {worktree_path}\n"
        f"Branch: {branch_name}\n"
        f"You can now make changes inside {worktree_path} without affecting the main branch."
    )


async def exit_worktree(worktree_path: str, keep_branch: bool = False) -> str:
    """
    Removes a git worktree created with `EnterWorktree`.

    Use `keep_branch=True` to preserve the branch for merging; default deletes it.
    Always clean up worktrees after use.
    """
    cwd = os.getcwd()

    if not os.path.isdir(worktree_path):
        raise RuntimeError(f"Worktree path does not exist: {worktree_path}")

    # Discover the branch name before removal
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

    # Remove the worktree
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
        raise RuntimeError(f"Failed to remove worktree: {rm_err.decode().strip()}")

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
                f"Could not delete branch {branch_name}: {del_err.decode().strip()}"
            )
    elif branch_name:
        lines.append(f"Branch kept: {branch_name} (merge or cherry-pick when ready)")

    return "\n".join(lines)


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
        raise RuntimeError(f"Failed to list worktrees: {stderr.decode().strip()}")

    output = stdout.decode().strip()
    return output if output else "No additional worktrees found."


# Set function names to PascalCase for tool display
enter_worktree.__name__ = "EnterWorktree"
exit_worktree.__name__ = "ExitWorktree"
list_worktrees.__name__ = "ListWorktrees"
