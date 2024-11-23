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
