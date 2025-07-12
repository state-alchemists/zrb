import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.util.cmd.command import run_command

if TYPE_CHECKING:
    from zrb.util.git_diff_model import DiffResult


async def get_diff(
    repo_dir: str,
    source_commit: str,
    current_commit: str,
    print_method: Callable[..., Any] = print,
) -> "DiffResult":
    """
    Get the difference between two commits in a Git repository.

    Args:
        repo_dir (str): The path to the Git repository.
        source_commit (str): The source commit hash or reference.
        current_commit (str): The current commit hash or reference.
        print_method (Callable[..., Any]): Method to print command output.

    Returns:
        DiffResult: An object containing lists of created, removed, and updated files.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    from zrb.util.git_diff_model import DiffResult

    cmd_result, exit_code = await run_command(
        cmd=["git", "diff", source_commit, current_commit],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
    lines = cmd_result.output.strip().split("\n")
    diff: dict[str, dict[str, bool]] = {}
    for line in lines:
        if not line.startswith("---") and not line.startswith("+++"):
            continue
        if line[4:6] != "a/" and line[4:6] != "b/":
            continue
        # line should contains something like `--- a/some-file.txt`
        file = line[6:]
        if file not in diff:
            diff[file] = {"plus": False, "minus": False}
        if line.startswith("---"):
            diff[file]["minus"] = True
        if line.startswith("+++"):
            diff[file]["plus"] = True
    return DiffResult(
        created=[
            file for file, state in diff.items() if state["plus"] and not state["minus"]
        ],
        removed=[
            file for file, state in diff.items() if not state["plus"] and state["minus"]
        ],
        updated=[
            file for file, state in diff.items() if state["plus"] and state["minus"]
        ],
    )


async def get_repo_dir(print_method: Callable[..., Any] = print) -> str:
    """
    Get the top-level directory of the Git repository.

    Args:
        print_method (Callable[..., Any]): Method to print command output.

    Returns:
        str: The absolute path to the repository's top-level directory.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    cmd_result, exit_code = await run_command(
        cmd=["git", "rev-parse", "--show-toplevel"],
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
    return os.path.abspath(cmd_result.output.strip())


async def get_current_branch(
    repo_dir: str, print_method: Callable[..., Any] = print
) -> str:
    """
    Get the current branch name of the Git repository.

    Args:
        repo_dir (str): The path to the Git repository.
        print_method (Callable[..., Any]): Method to print command output.

    Returns:
        str: The name of the current branch.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    cmd_result, exit_code = await run_command(
        cmd=["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
    return cmd_result.output.strip()


async def get_branches(
    repo_dir: str, print_method: Callable[..., Any] = print
) -> list[str]:
    """
    Get a list of all branches in the Git repository.

    Args:
        repo_dir (str): The path to the Git repository.
        print_method (Callable[..., Any]): Method to print command output.

    Returns:
        list[str]: A list of branch names.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    cmd_result, exit_code = await run_command(
        cmd=["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
    return [
        branch.lstrip("*").strip() for branch in cmd_result.output.strip().split("\n")
    ]


async def delete_branch(
    repo_dir: str, branch_name: str, print_method: Callable[..., Any] = print
) -> str:
    """
    Delete a branch in the Git repository.

    Args:
        repo_dir (str): The path to the Git repository.
        branch_name (str): The name of the branch to delete.
        print_method (Callable[..., Any]): Method to print command output.

    Returns:
        str: The output of the git command.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    cmd_result, exit_code = await run_command(
        cmd=["git", "branch", "-D", branch_name],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
    return cmd_result.output.strip()


async def add(repo_dir: str, print_method: Callable[..., Any] = print):
    """
    Add all changes to the Git staging area.

    Args:
        repo_dir (str): The path to the Git repository.
        print_method (Callable[..., Any]): Method to print command output.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    _, exit_code = await run_command(
        cmd=["git", "add", ".", "-A"],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")


async def commit(
    repo_dir: str, message: str, print_method: Callable[..., Any] = print
) -> str:
    """
    Commit changes in the Git repository.

    Args:
        repo_dir (str): The path to the Git repository.
        message (str): The commit message.
        print_method (Callable[..., Any]): Method to print command output.

    Raises:
        Exception: If the git command returns a non-zero exit code, unless it's
            the "nothing to commit" message.
    """
    cmd_result, exit_code = await run_command(
        cmd=["git", "commit", "-m", message],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        ignored_error_message = "nothing to commit, working tree clean"
        if (
            ignored_error_message not in cmd_result.error
            and ignored_error_message not in cmd_result.output
        ):
            raise Exception(f"Non zero exit code: {exit_code}")


async def pull(
    repo_dir: str, remote: str, branch: str, print_method: Callable[..., Any] = print
) -> str:
    """
    Pull changes from a remote repository and branch.

    Args:
        repo_dir (str): The path to the Git repository.
        remote (str): The name of the remote.
        branch (str): The name of the branch.
        print_method (Callable[..., Any]): Method to print command output.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    _, exit_code = await run_command(
        cmd=["git", "pull", remote, branch],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")


async def push(
    repo_dir: str, remote: str, branch: str, print_method: Callable[..., Any] = print
) -> str:
    """
    Push changes to a remote repository and branch.

    Args:
        repo_dir (str): The path to the Git repository.
        remote (str): The name of the remote.
        branch (str): The name of the branch.
        print_method (Callable[..., Any]): Method to print command output.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    _, exit_code = await run_command(
        cmd=["git", "push", "-u", remote, branch],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
