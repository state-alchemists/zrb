import subprocess

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Mapping


@typechecked
class ModificationState:
    def __init__(self):
        self.plus: bool = False
        self.minus: bool = False


@typechecked
def get_modified_file_states(commit: str) -> Mapping[str, ModificationState]:
    exit_status, output = subprocess.getstatusoutput(f"git show {commit}")
    if exit_status != 0:
        raise Exception(output)
    lines = output.split("\n")
    modified_files: Mapping[str, ModificationState] = {}
    for line in lines:
        if not line.startswith("---") and not line.startswith("+++"):
            continue
        if line[4:6] != "a/" and line[4:6] != "b/":
            continue
        # line should contains something like `--- a/some-file.txt`
        file = line[6:]
        if file not in modified_files:
            modified_files[file] = ModificationState()
        modification_state = modified_files[file]
        if line.startswith("---"):
            modification_state.minus = True
        if line.startswith("+++"):
            modification_state.plus = True
    return modified_files
