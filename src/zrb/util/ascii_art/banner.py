"""Resolution of the ASCII art shown beside the TUI help panel.

Composition lives in `zrb.util.cli.help_panel`, which lays the art out against
the current terminal width; this module only answers "which art, and what is
in it".
"""

import os
import random

from zrb.config.config import CFG


def _get_default_banner_search_path() -> list[str]:
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
    if art is not None:
        if os.path.isfile(art):
            with open(art, "r", encoding="utf-8") as f:
                return f.read()
        # Check in search paths
        for search_path in _get_default_banner_search_path():
            art_path = os.path.join(search_path, CFG.ASCII_ART_DIR, f"{art}.txt")
            if os.path.isfile(art_path):
                with open(art_path, "r", encoding="utf-8") as f:
                    return f.read()
        # Check in builtin art folder
        cwd = os.path.dirname(__file__)
        builtin_art_path = os.path.join(cwd, "art", f"{art}.txt")
        if os.path.isfile(builtin_art_path):
            with open(builtin_art_path, "r", encoding="utf-8") as f:
                return f.read()

    # If no specific art requested, or if requested art not found, find a random one.
    all_art_files = []
    # Collect from search paths
    for search_path in _get_default_banner_search_path():
        art_dir = os.path.join(search_path, CFG.ASCII_ART_DIR)
        if os.path.isdir(art_dir):
            for filename in os.listdir(art_dir):
                if filename.endswith(".txt"):
                    all_art_files.append(os.path.join(art_dir, filename))
    # Collect from builtin art folder
    cwd = os.path.dirname(__file__)
    builtin_art_dir = os.path.join(cwd, "art")
    if os.path.isdir(builtin_art_dir):
        for filename in os.listdir(builtin_art_dir):
            if filename.endswith(".txt"):
                all_art_files.append(os.path.join(builtin_art_dir, filename))
    if all_art_files:
        random_file_path = random.choice(all_art_files)
        with open(random_file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""
