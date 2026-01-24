import os

import pytest

from zrb.util.ascii_art.banner import create_banner


@pytest.fixture
def temp_art_file(tmp_path):
    f = tmp_path / "art.txt"
    f.write_text("ASCII\nART")
    return str(f)


def test_create_banner_simple(temp_art_file):
    text = "Hello World"
    banner = create_banner(temp_art_file, text)
    assert "ASCII" in banner
    assert "ART" in banner
    assert "Hello World" in banner


def test_create_banner_empty_ascii():
    text = "Hello World"
    # This will return a random art, so we just check for the text
    banner = create_banner(None, text)
    assert "Hello World" in banner


def test_create_banner_empty_text(temp_art_file):
    banner = create_banner(temp_art_file, "")
    assert "ASCII" in banner
    assert "ART" in banner
