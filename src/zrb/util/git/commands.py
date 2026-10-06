import os
from collections.abc import Callable
from typing import Any

from zrb.util.cmd.command import run_command
from zrb.util.git.diff_model import DiffResult


async def get_diff(
    repo_dir: str,
    source_commit: str,
    current_commit: str,
    print_method: Callable[..., Any] = print,
) -> "DiffResult":
    """Diff `source_commit`..`current_commit`, sorted into created/removed/updated files."""
    cmd_result, exit_code = await run_command(
        cmd=["git", "diff", source_commit, current_commit],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
    diff = _parse_diff_file_markers(cmd_result.output.strip().split("\n"))
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


def _parse_diff_file_markers(lines: list[str]) -> dict[str, dict[str, bool]]:
    """Map each path in a unified diff to which of its `---`/`+++` sides appeared.

    A path with only `+++` was created, only `---` removed, and both updated.
    """
    diff: dict[str, dict[str, bool]] = {}
    for line in lines:
        is_minus = line.startswith("---")
        if not is_minus and not line.startswith("+++"):
            continue
        # line should contains something like `--- a/some-file.txt`
        if line[4:6] not in ("a/", "b/"):
            continue
        state = diff.setdefault(line[6:], {"plus": False, "minus": False})
        state["minus" if is_minus else "plus"] = True
    return diff


async def get_repo_dir(print_method: Callable[..., Any] = print) -> str:
    """The repository's top-level (root) directory, as an absolute path."""
    cmd_result, exit_code = await run_command(
        cmd=["git", "rev-parse", "--show-toplevel"],
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
    return os.path.abspath(cmd_result.output.strip())


async def get_current_branch(
    repo_dir: str, print_method: Callable[..., Any] = print
) -> str:
    """The current branch name."""
    cmd_result, exit_code = await run_command(
        cmd=["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
    return cmd_result.output.strip()


async def get_branches(
    repo_dir: str, print_method: Callable[..., Any] = print
) -> list[str]:
    """All local branch names."""
    cmd_result, exit_code = await run_command(
        cmd=["git", "branch"],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
    return [
        _parse_branch_name(branch)
        for branch in cmd_result.output.strip().split("\n")
        if branch.strip()
    ]


def _parse_branch_name(branch: str) -> str:
    return branch.lstrip("*+").strip()


async def get_worktrees(
    repo_dir: str, print_method: Callable[..., None] = print
) -> dict[str, list[str]]:
    """Map each checked-out local branch to all its worktree paths."""
    cmd_result, exit_code = await run_command(
        cmd=[
            "git",
            "-c",
            "core.quotePath=true",
            "worktree",
            "list",
            "--porcelain",
        ],
        cwd=repo_dir,
        print_method=print_method,
        max_output_line=0,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
    return _parse_worktrees(cmd_result.output)


def _parse_worktrees(output: str) -> dict[str, list[str]]:
    worktrees: dict[str, list[str]] = {}
    path = ""
    for line in (*output.splitlines(), ""):
        if line.startswith("worktree "):
            path = _parse_git_path(line.removeprefix("worktree "))
        elif line.startswith("branch refs/heads/") and path:
            branch = line.removeprefix("branch refs/heads/")
            worktrees.setdefault(branch, []).append(path)
        elif not line:
            path = ""
    return worktrees


def _parse_git_path(path: str) -> str:
    if not path.startswith('"'):
        return path
    if len(path) < 2 or not path.endswith('"'):
        raise ValueError(f"Invalid Git path: {path}")

    escaped = path[1:-1]
    decoded = bytearray()
    index = 0
    escapes = {
        "a": 0x07,
        "b": 0x08,
        "t": 0x09,
        "n": 0x0A,
        "v": 0x0B,
        "f": 0x0C,
        "r": 0x0D,
        "\\": 0x5C,
        '"': 0x22,
    }
    while index < len(escaped):
        char = escaped[index]
        if char != "\\":
            decoded.extend(char.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index >= len(escaped):
            raise ValueError(f"Invalid Git path: {path}")
        char = escaped[index]
        if char in escapes:
            decoded.append(escapes[char])
            index += 1
            continue
        if char not in "01234567":
            raise ValueError(f"Invalid Git path: {path}")
        end = index
        while end < len(escaped) and end < index + 3 and escaped[end] in "01234567":
            end += 1
        decoded.append(int(escaped[index:end], 8))
        index = end
    return decoded.decode("utf-8")


async def remove_worktree(
    repo_dir: str, worktree_path: str, print_method: Callable[..., None] = print
) -> None:
    """Remove a clean linked worktree and its checked-out directory."""
    _, exit_code = await run_command(
        cmd=["git", "worktree", "remove", worktree_path],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")


async def is_branch_merged(
    repo_dir: str,
    branch_name: str,
    target: str = "HEAD",
    print_method: Callable[..., Any] = print,
) -> bool:
    """Whether `branch_name` is merged into `target` (default `HEAD`)."""
    cmd_result, exit_code = await run_command(
        cmd=["git", "branch", "--merged", target],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
    merged_branches = [
        _parse_branch_name(branch)
        for branch in cmd_result.output.strip().split("\n")
        if branch.strip()
    ]
    return branch_name in merged_branches


async def delete_branch(
    repo_dir: str, branch_name: str, print_method: Callable[..., Any] = print
) -> str:
    """Delete `branch_name` (must already be merged — plain `-d`, not `-D`)."""
    cmd_result, exit_code = await run_command(
        cmd=["git", "branch", "-d", branch_name],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
    return cmd_result.output.strip()


async def add(repo_dir: str, print_method: Callable[..., Any] = print):
    """Stage every change in `repo_dir` (`git add . -A`)."""
    _, exit_code = await run_command(
        cmd=["git", "add", ".", "-A"],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")


async def commit(
    repo_dir: str, message: str, print_method: Callable[..., Any] = print
) -> None:
    """Commit staged changes with `message`.

    A "nothing to commit, working tree clean" failure is swallowed.
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
            raise RuntimeError(f"Non zero exit code: {exit_code}")


async def pull(
    repo_dir: str, remote: str, branch: str, print_method: Callable[..., Any] = print
) -> None:
    """Pull `branch` from `remote`."""
    _, exit_code = await run_command(
        cmd=["git", "pull", remote, branch],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")


async def push(
    repo_dir: str, remote: str, branch: str, print_method: Callable[..., Any] = print
) -> None:
    """Push `branch` to `remote`, setting it as the upstream (`-u`)."""
    _, exit_code = await run_command(
        cmd=["git", "push", "-u", remote, branch],
        cwd=repo_dir,
        print_method=print_method,
    )
    if exit_code != 0:
        raise RuntimeError(f"Non zero exit code: {exit_code}")
