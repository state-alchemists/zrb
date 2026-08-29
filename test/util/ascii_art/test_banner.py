import os
from unittest.mock import patch

import pytest

from zrb.util.ascii_art.banner import get_ascii_art


@pytest.fixture
def temp_art_file(tmp_path):
    f = tmp_path / "art.txt"
    f.write_text("ASCII\nART")
    return str(f)


def test_get_ascii_art_reads_a_path(temp_art_file):
    art = get_ascii_art(temp_art_file)
    assert "ASCII" in art
    assert "ART" in art


def test_get_ascii_art_reads_a_builtin_name():
    art = get_ascii_art("default")
    assert art.strip() != ""


def test_get_ascii_art_reads_a_name_from_the_art_dir(tmp_path, monkeypatch):
    art_dir = tmp_path / ".zrb" / "ascii-art"
    art_dir.mkdir(parents=True)
    (art_dir / "mine.txt").write_text("MY ART")
    monkeypatch.chdir(tmp_path)

    assert "MY ART" in get_ascii_art("mine")


def test_get_ascii_art_falls_back_to_a_random_art():
    # A name that matches nothing still yields art, never an empty panel.
    res = get_ascii_art("/tmp/nonexistent_art_xyz_123.txt")
    assert isinstance(res, str)
    assert res.strip() != ""


def test_get_ascii_art_without_a_name_picks_something():
    assert get_ascii_art().strip() != ""


def test_get_ascii_art_returns_empty_when_no_art_exists(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with patch("os.path.isdir", return_value=False):
        assert get_ascii_art("nope") == ""


def test_get_default_banner_search_path_value_error():
    from zrb.util.ascii_art.banner import get_default_banner_search_path

    with patch("os.path.commonpath", side_effect=ValueError("different drives")):
        res = get_default_banner_search_path()
        assert len(res) >= 1


def test_get_default_banner_search_path_walks_up_to_home(monkeypatch, tmp_path):
    from zrb.util.ascii_art.banner import get_default_banner_search_path

    home = tmp_path / "home"
    nested = home / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(nested)

    res = get_default_banner_search_path()
    assert os.path.abspath(str(nested)) in res
    assert os.path.abspath(str(home)) in res
