import os
import random
import re

from zrb.config.config import CFG

ANSI_ESCAPE = re.compile(r"(?:\x1B|\\033)(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _get_visible_length(text: str) -> int:
    """Return the visible length of a string, excluding ANSI escape sequences."""
    return len(ANSI_ESCAPE.sub("", text))


def create_banner(
    art: str | None = None,
    text: str | None = None,
    max_width: int | None = None,
) -> str:
    art_content = _get_art_only(art)

    if text is None or text.strip() == "":
        return art_content

    art_lines = art_content.splitlines()
    if not art_lines:
        return text

    max_art_length = max(_get_visible_length(line) for line in art_lines)

    # Hide the art if the combined width would overflow the terminal: the
    # separator is 2 spaces and we compare against the widest text line.
    if max_width is not None:
        max_text_length = max(
            (_get_visible_length(line) for line in text.splitlines()), default=0
        )
        if max_art_length + 2 + max_text_length > max_width:
            return text

    # Pad all art lines to the same visual length
    padded_art_lines = [
        line + " " * (max_art_length - _get_visible_length(line)) for line in art_lines
    ]

    text_lines = text.splitlines()

    combined_lines = []

    max_lines = max(len(padded_art_lines), len(text_lines))

    art_offset = (max_lines - len(padded_art_lines)) // 2
    text_offset = (max_lines - len(text_lines)) // 2

    for i in range(max_lines):
        art_index = i - art_offset
        if 0 <= art_index < len(padded_art_lines):
            art_line = padded_art_lines[art_index]
        else:
            art_line = " " * max_art_length

        text_index = i - text_offset
        if 0 <= text_index < len(text_lines):
            text_line = text_lines[text_index]
        else:
            text_line = ""

        combined_line = art_line + "  " + text_line
        combined_lines.append(combined_line)

    return "\n".join(combined_lines)


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


def _get_art_only(art: str | None = None) -> str:
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
