"""Resolution of the ASCII art shown beside the TUI help panel (laid out by
`zrb.util.cli.help_panel`)."""

import os
import random

from zrb.config.config import CFG
from zrb.util.dir_search import get_dirs_up_to_home


def get_default_banner_search_path() -> list[str]:
    return get_dirs_up_to_home(
        os.path.abspath(os.getcwd()), os.path.abspath(os.path.expanduser("~"))
    )


def get_ascii_art(art: str | None = None) -> str:
    """Resolve `art` (a path or a name) to its content, or pick a random one.

    Resolution order: literal path, then `{search path}/{ASCII_ART_DIR}/{art}.txt`
    walking up from the CWD to `$HOME`, then the built-in art folder. A name that
    matches nothing falls back to a random available art, so callers that need a
    stable image across re-renders must resolve once and keep the result.
    """
    art_dirs = [
        os.path.join(search_path, CFG.ASCII_ART_DIR)
        for search_path in get_default_banner_search_path()
    ] + [os.path.join(os.path.dirname(__file__), "art")]
    if art is not None:
        candidates = [art] + [os.path.join(d, f"{art}.txt") for d in art_dirs]
        for art_path in candidates:
            if os.path.isfile(art_path):
                return _read(art_path)
    all_art_files = [
        os.path.join(art_dir, filename)
        for art_dir in art_dirs
        if os.path.isdir(art_dir)
        for filename in os.listdir(art_dir)
        if filename.endswith(".txt")
    ]
    if all_art_files:
        return _read(random.choice(all_art_files))
    return ""


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
