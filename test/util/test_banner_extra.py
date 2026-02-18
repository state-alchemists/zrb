import os
from unittest.mock import patch

from zrb.util.ascii_art.banner import _get_art_only, create_banner


def test_create_banner_no_art_lines():
    # If _get_art_only returns empty string
    with patch("zrb.util.ascii_art.banner._get_art_only", return_value=""):
        assert create_banner(text="Hello") == "Hello"


def test_create_banner_vertical_offset():
    # Art has 1 line, text has 3 lines
    art = "ART"
    text = "T1\nT2\nT3"
    with patch("zrb.util.ascii_art.banner._get_art_only", return_value=art):
        result = create_banner(art=art, text=text)
        # ART should be on line 2 (offset = (3 - 1) // 2 = 1)
        lines = result.splitlines()
        assert "ART" in lines[1]
        assert "   " in lines[0]  # Padded art line on line 1


def test_get_art_only_file_path():
    # Create a temp file
    file_path = "temp_art_literal.txt"
    with open(file_path, "w") as f:
        f.write("TEMP ART")
    try:
        assert _get_art_only(file_path) == "TEMP ART"
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_get_art_only_not_found():
    # Should return a random art if requested art not found
    # We mock os.path.isdir to return True for builtin art dir but empty
    with patch("os.path.isdir", return_value=False), patch(
        "os.path.isfile", return_value=False
    ):
        assert _get_art_only("nonexistent") == ""
