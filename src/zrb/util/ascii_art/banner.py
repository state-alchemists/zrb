import os
import random

from zrb.config.config import CFG


def create_banner(art: str | None = None, text: str | None = None) -> str:
    # First get art using _get_art_only
    art_content = _get_art_only(art)

    # If no text provided, just return the art
    if text is None or text.strip() == "":
        return art_content

    # Find the longest line in the art, make every line has the same length
    art_lines = art_content.splitlines()
    if not art_lines:
        return text

    # Find the maximum line length in the art
    max_art_length = max(len(line) for line in art_lines)

    # Pad all art lines to the same length
    padded_art_lines = [line.ljust(max_art_length) for line in art_lines]

    # Split text into lines
    text_lines = text.splitlines()

    # Combine art and text lines
    combined_lines = []

    # Determine the maximum number of lines we need
    max_lines = max(len(padded_art_lines), len(text_lines))

    # Calculate vertical offsets for centering
    art_offset = (max_lines - len(padded_art_lines)) // 2
    text_offset = (max_lines - len(text_lines)) // 2

    for i in range(max_lines):
        # Get art line (or empty string if we've run out of art lines)
        art_index = i - art_offset
        if 0 <= art_index < len(padded_art_lines):
            art_line = padded_art_lines[art_index]
        else:
            art_line = " " * max_art_length

        # Get text line (or empty string if we've run out of text lines)
        text_index = i - text_offset
        if 0 <= text_index < len(text_lines):
            text_line = text_lines[text_index]
        else:
            text_line = ""

        # Combine art and text lines
        combined_line = art_line + "  " + text_line
        combined_lines.append(combined_line)

    # Return the combined result
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
    # If art name is provided, try to find it.
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
    # If any art files were found, pick one at random.
    if all_art_files:
        random_file_path = random.choice(all_art_files)
        with open(random_file_path, "r", encoding="utf-8") as f:
            return f.read()
    # If no art found at all, return empty string.
    return ""
