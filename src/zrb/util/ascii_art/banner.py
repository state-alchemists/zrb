"""Resolution of the ASCII art shown beside the TUI help panel.

Composition lives in `zrb.util.cli.help_panel`, which lays the art out against
the current terminal width; this module only answers "which art, and what is
in it".
"""

import os
import random

from zrb.config.config import CFG


def get_default_banner_search_path() -> list[str]:
    current_path = os.path.abspath(os.getcwd())
    home_path = os.path.abspath(os.path.expanduser("~"))
    search_paths = [current_path]
    try:
        if os.path.commonpath([current_path, home_path]) == home_path:
            temp_path = current_path
            while temp_path != home_path:
                new_temp_path = os.path.dirname(temp_path)
                if new_temp_path == temp_path:
                    break
                temp_path = new_temp_path
                search_paths.append(temp_path)
    except ValueError:
        pass
    return search_paths


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
