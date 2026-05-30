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


from unittest.mock import patch


def test_create_banner_empty_art():
    from zrb.util.ascii_art.banner import create_banner

    with patch("zrb.util.ascii_art.banner._get_art_only", return_value=""):
        res = create_banner(None, "text")
        assert res == "text"


def test_create_banner_max_width_hides_art_when_overflow():
    with patch("zrb.util.ascii_art.banner._get_art_only", return_value="ASCII\nART"):
        # art_width=5, separator=2, text_width=11 → 18 columns total.
        # max_width=10 forces the art to be dropped.
        res = create_banner(None, "Hello World", max_width=10)
        assert res == "Hello World"
        assert "ASCII" not in res


def test_create_banner_max_width_keeps_art_when_fits():
    with patch("zrb.util.ascii_art.banner._get_art_only", return_value="ASCII\nART"):
        res = create_banner(None, "Hi", max_width=80)
        assert "ASCII" in res
        assert "Hi" in res


def test_get_art_only_file_not_found():
    from zrb.util.ascii_art.banner import _get_art_only

    # Provide a non-existent absolute path
    res = _get_art_only("/tmp/nonexistent_art_xyz_123.txt")
    # Should fallback to random or empty
    assert isinstance(res, str)


def test_get_default_banner_search_path_value_error():
    from zrb.util.ascii_art.banner import _get_default_banner_search_path

    with patch("os.path.commonpath", side_effect=ValueError("different drives")):
        res = _get_default_banner_search_path()
        assert len(res) >= 1
