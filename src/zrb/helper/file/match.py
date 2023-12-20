from zrb.helper.typing import List, Iterable
from zrb.helper.typecheck import typechecked
import fnmatch
import glob


@typechecked
def get_file_names(
    glob_path: str, glob_ignored_paths: Iterable[str]
) -> List[str]:
    matches = []
    for file in glob.glob(glob_path, recursive=True):
        should_ignore = False
        for ignored_path in glob_ignored_paths:
            if fnmatch.fnmatch(file, ignored_path):
                should_ignore = True
                break
        if not should_ignore:
            matches.append(file)
    return matches
