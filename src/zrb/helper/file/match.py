import fnmatch
import glob
from collections.abc import Iterable

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.file.match", attrs=["dark"]))


@typechecked
def get_file_names(glob_path: str, glob_ignored_paths: Iterable[str]) -> list[str]:
    matches = []
    for file in glob.glob(glob_path, recursive=True):
        should_ignore = any(
            fnmatch.fnmatch(file, ignored_path)
            or fnmatch.fnmatch(file, ignored_path + "**")
            for ignored_path in glob_ignored_paths
        )
        if not should_ignore:
            matches.append(file)
    return matches
