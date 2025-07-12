import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.util.cmd.command import run_command
from zrb.util.file import read_file, write_file

if TYPE_CHECKING:
    from zrb.util.git_subtree_model import SubTreeConfig


def load_config(repo_dir: str):
    """
    Load the subtree configuration from subtrees.json.

    Args:
        repo_dir (str): The path to the Git repository.

    Returns:
        SubTreeConfig: The loaded subtree configuration.
    """
    from zrb.util.git_subtree_model import SubTreeConfig

    file_path = os.path.join(repo_dir, "subtrees.json")
    if not os.path.exists(file_path):
        return SubTreeConfig(data={})
    return SubTreeConfig.model_validate_json(read_file(file_path))


def save_config(repo_dir: str, config: "SubTreeConfig"):
    """
    Save the subtree configuration to subtrees.json.

    Args:
        repo_dir (str): The path to the Git repository.
        config (SubTreeConfig): The subtree configuration to save.
    """
    file_path = os.path.join(repo_dir, "subtrees.json")
    write_file(file_path, config.model_dump_json(indent=2))


async def add_subtree(
    repo_dir: str,
    name: str,
    repo_url: str,
    branch: str,
    prefix: str,
    print_method: Callable[..., Any] = print,
):
    """
    Add a Git subtree to the repository.

    Args:
        repo_dir (str): The path to the Git repository.
        name (str): The name for the subtree configuration.
        repo_url (str): The URL of the subtree repository.
        branch (str): The branch of the subtree repository.
        prefix (str): The local path where the subtree will be added.
        print_method (Callable[..., Any]): Method to print command output.

    Raises:
        ValueError: If the prefix directory already exists or subtree config
            name already exists.
        Exception: If the git command returns a non-zero exit code.
    """
    from zrb.util.git_subtree_model import SingleSubTreeConfig

    config = load_config(repo_dir)
    if os.path.isdir(prefix):
        raise ValueError(f"Directory exists: {prefix}")
    if name in config.data:
        raise ValueError(f"Subtree config already exists: {name}")
    _, exit_code = await run_command(
        cmd=[
            "git",
            "subtree",
            "add",
            "--prefix",
            prefix,
            repo_url,
            branch,
        ],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
    config.data[name] = SingleSubTreeConfig(
        repo_url=repo_url, branch=branch, prefix=prefix
    )
    save_config(repo_dir, config)


async def pull_subtree(
    repo_dir: str,
    prefix: str,
    repo_url: str,
    branch: str,
    print_method: Callable[..., Any] = print,
):
    """
    Pull changes from a Git subtree.

    Args:
        repo_dir (str): The path to the Git repository.
        prefix (str): The local path of the subtree.
        repo_url (str): The URL of the subtree repository.
        branch (str): The branch of the subtree repository.
        print_method (Callable[..., Any]): Method to print command output.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    _, exit_code = await run_command(
        cmd=[
            "git",
            "subtree",
            "pull",
            "--prefix",
            prefix,
            repo_url,
            branch,
        ],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")


async def push_subtree(
    repo_dir: str,
    prefix: str,
    repo_url: str,
    branch: str,
    print_method: Callable[..., Any] = print,
):
    """
    Push changes to a Git subtree.

    Args:
        repo_dir (str): The path to the Git repository.
        prefix (str): The local path of the subtree.
        repo_url (str): The URL of the subtree repository.
        branch (str): The branch of the subtree repository.
        print_method (Callable[..., Any]): Method to print command output.

    Raises:
        Exception: If the git command returns a non-zero exit code.
    """
    _, exit_code = await run_command(
        cmd=[
            "git",
            "subtree",
            "push",
            "--prefix",
            prefix,
            repo_url,
            branch,
        ],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
