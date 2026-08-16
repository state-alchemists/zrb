import json
import os
from collections.abc import Callable
from typing import Any

from zrb.util.cmd.command import run_command
from zrb.util.file import read_file, write_file
from zrb.util.git_subtree_model import SingleSubTreeConfig, SubTreeConfig


def load_config(repo_dir: str):
    """Load `subtrees.json` from `repo_dir`, or an empty config if it doesn't exist yet."""
    file_path = os.path.join(repo_dir, "subtrees.json")
    if not os.path.exists(file_path):
        return SubTreeConfig(data={})
    raw_data = json.loads(read_file(file_path))
    return SubTreeConfig(
        data={k: SingleSubTreeConfig(**v) for k, v in raw_data.get("data", {}).items()}
    )


def save_config(repo_dir: str, config: "SubTreeConfig"):
    """Write `config` to `subtrees.json` in `repo_dir`."""
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
    """Add a subtree at `prefix` and record it under `name` in `subtrees.json`.

    Rejects a `prefix` that already exists or a `name` already configured —
    `git subtree add` itself would just as happily clobber either.
    """
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
        raise RuntimeError(f"Non zero exit code: {exit_code}")
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
    """Pull `branch` from `repo_url` into the subtree at `prefix`."""
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
        raise RuntimeError(f"Non zero exit code: {exit_code}")


async def push_subtree(
    repo_dir: str,
    prefix: str,
    repo_url: str,
    branch: str,
    print_method: Callable[..., Any] = print,
):
    """Push the subtree at `prefix` to `branch` on `repo_url`."""
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
        raise RuntimeError(f"Non zero exit code: {exit_code}")
