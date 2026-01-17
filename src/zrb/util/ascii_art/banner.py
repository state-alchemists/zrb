import os
import random


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

    for i in range(max_lines):
        # Get art line (or empty string if we've run out of art lines)
        art_line = (
            padded_art_lines[i] if i < len(padded_art_lines) else " " * max_art_length
        )

        # Get text line (or empty string if we've run out of text lines)
        text_line = text_lines[i] if i < len(text_lines) else ""

        # Combine art and text lines
        combined_line = art_line + "  " + text_line
        combined_lines.append(combined_line)

    # Return the combined result
    return "\n".join(combined_lines)


def _get_art_only(art: str | None = None) -> str:
    # If name is provided
    if art is not None:
        # 1) name is a file, load the content of the file, return
        expanded_name = os.path.expanduser(art)
        if os.path.isfile(expanded_name):
            with open(expanded_name, "r") as f:
                return f.read()

        # 2) name is a string, but not a file
        # Check if art/name.txt exists in the script directory
        cwd = os.path.dirname(__file__)
        art_path = os.path.join(cwd, "art", f"{art}.txt")
        if os.path.isfile(art_path):
            with open(art_path, "r") as f:
                return f.read()

    # 3) otherwise load random file from art/ directory
    cwd = os.path.dirname(__file__)
    art_dir = os.path.join(cwd, "art")
    # Get all .txt files in the art directory
    try:
        art_files = [f for f in os.listdir(art_dir) if f.endswith(".txt")]
    except FileNotFoundError:
        # If art directory doesn't exist, return empty string
        return ""
    if not art_files:
        return ""
    # Select a random file
    random_file = random.choice(art_files)
    random_file_path = os.path.join(art_dir, random_file)
    with open(random_file_path, "r") as f:
        return f.read()
