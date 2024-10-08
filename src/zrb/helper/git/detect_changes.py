import subprocess
from collections.abc import Mapping

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.git.detect_changes", attrs=["dark"]))


@typechecked
class ModificationState:
    def __init__(self):
        self.plus: bool = False
        self.minus: bool = False


@typechecked
def get_modified_file_states(
    current_commit: str, source_commit: str = "main"
) -> Mapping[str, ModificationState]:
    # git show b176b5a main
    exit_status, output = subprocess.getstatusoutput(
        f"git diff {source_commit} {current_commit}"
    )
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
