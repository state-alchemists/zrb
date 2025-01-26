import os
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from zrb.util.cmd.command import run_command


class DiffResult(BaseModel):
    created: list[str]
    removed: list[str]
    updated: list[str]


async def get_diff(
    repo_dir: str,
    source_commit: str,
    current_commit: str,
    print_method: Callable[..., Any] = print,
) -> DiffResult:
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
    cmd_result, exit_code = await run_command(
        cmd=["git", "branch", "-D", branch_name],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
    return cmd_result.output.strip()


async def add(repo_dir: str, print_method: Callable[..., Any] = print):
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
    _, exit_code = await run_command(
        cmd=["git", "push", "-u", remote, branch],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise Exception(f"Non zero exit code: {exit_code}")
