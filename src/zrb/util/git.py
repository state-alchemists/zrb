import subprocess

from pydantic import BaseModel


class DiffResult(BaseModel):
    created: list[str]
    removed: list[str]
    updated: list[str]


def get_diff(source_commit: str, current_commit: str) -> DiffResult:
    # git show b176b5a main
    exit_status, output = subprocess.getstatusoutput(
        f"git diff {source_commit} {current_commit}"
    )
    if exit_status != 0:
        raise Exception(output)
    lines = output.split("\n")
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


def get_repo_dir() -> str:
    # Run the Git command to get the repository's top-level directory
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    # Return the directory path
    return result.stdout.strip()


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_branches() -> list[str]:
    result = subprocess.run(
        ["git", "branch"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return [branch.lstrip("*").strip() for branch in result.stdout.strip().split("\n")]


def delete_branch(branch_name: str) -> str:
    result = subprocess.run(
        ["git", "branch", "-D", branch_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def add() -> str:
    result = subprocess.run(
        ["git", "add", ".", "-A"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result


def commit(message: str) -> str:
    result = subprocess.run(
        ["git", "commit", "-m", message],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result


def pull(remote: str, branch: str) -> str:
    result = subprocess.run(
        ["git", "pull", remote, branch],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result


def push(remote: str, branch: str) -> str:
    result = subprocess.run(
        ["git", "push", "-u", remote, branch],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result
