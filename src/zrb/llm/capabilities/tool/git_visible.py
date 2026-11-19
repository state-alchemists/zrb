"""What git would show, for the tools that answer "which files are here?".

`LS`, `Glob` and `AnalyzeCode` all report on the same tree, so they have to
agree about what counts as part of it. A listing that hides generated output
while Glob returns it, or an analysis run that reads and bills for files the
repository refuses to track, makes one directory look like two repositories.

A path survives only if git lists it: tracked, or untracked but not ignored.
When the directory is not inside a checkout, or git cannot run, nothing is
filtered — a missing git is not evidence that every file is ignored.
"""

import os
import subprocess

from zrb.config.config import CFG


def git_visible_files(dir_path: str) -> set[str] | None:
    """Paths git would show under *dir_path*, relative to it.

    ``None`` when this is not a checkout or git is unavailable, so the caller
    keeps the unfiltered walk instead of hiding everything.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                dir_path,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            timeout=CFG.LLM_GIT_CMD_TIMEOUT / 1000,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    # `-z` gives each path raw and NUL-terminated. The line-oriented default
    # C-quotes anything unusual, so `café.py` would arrive as
    # `"caf\303\251.py"` and never match the name on disk.
    #
    # Bytes are decoded with `os.fsdecode` rather than by the subprocess: a
    # filename is not required to be valid UTF-8, and `text=True` would raise
    # on one, turning an unusual name into a broken tool. `fsdecode` applies
    # the same surrogateescape the walk's own names carry, so the two sides
    # compare equal.
    stdout = os.fsdecode(result.stdout)
    return {
        os.path.normpath(path.replace("/", os.sep))
        for path in stdout.split("\x00")
        if path
    }


def without_gitignored(dir_path: str, paths: list[str]) -> list[str]:
    """Drop the paths `.gitignore` hides, in their original order.

    *paths* are relative to *dir_path*, the same frame `git_visible_files`
    reports in.
    """
    visible = git_visible_files(dir_path)
    if visible is None:
        return paths
    return [path for path in paths if os.path.normpath(path) in visible]
