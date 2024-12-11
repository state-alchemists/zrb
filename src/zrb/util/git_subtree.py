import os
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from zrb.util.cmd.command import run_command


class SingleSubTreeConfig(BaseModel):
    repo_url: str
    branch: str
    prefix: str


class SubTreeConfig(BaseModel):
    data: dict[str, SingleSubTreeConfig]


def load_config(repo_dir: str) -> SubTreeConfig:
    file_path = os.path.join(repo_dir, "subtrees.json")
    if not os.path.exists(file_path):
        return SubTreeConfig(data={})
    with open(file_path, "r") as f:
        return SubTreeConfig.model_validate_json(f.read())


def save_config(repo_dir: str, config: SubTreeConfig):
    file_path = os.path.join(repo_dir, "subtrees.json")
    with open(file_path, "w") as f:
        f.write(config.model_dump_json(indent=2))


async def add_subtree(
    repo_dir: str,
    name: str,
    repo_url: str,
    branch: str,
    prefix: str,
    log_method: Callable[..., Any] = print,
):
    config = load_config()
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
        log_method=log_method,
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
    log_method: Callable[..., Any] = print,
):
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
        log_method=log_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")


async def push_subtree(
    repo_dir: str,
    prefix: str,
    repo_url: str,
    branch: str,
    log_method: Callable[..., Any] = print,
):
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
        log_method=log_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
