"""Tests for util/dir_search.py — covers happy paths and exception fallbacks."""

from pathlib import Path
from unittest.mock import patch

from zrb.util.dir_search import (
    get_dirs_up_to_home,
    get_upward_dirs,
    scan_plugin_dirs,
)


def test_get_upward_dirs_returns_root_to_start(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    result = get_upward_dirs(nested)
    # Result is root → start_dir; last element must be the resolved start_dir
    assert result[-1] == nested.resolve()
    # Parents appear in increasing depth
    assert nested.resolve().parent in result


def test_get_upward_dirs_falls_back_on_exception(caplog):
    with patch(
        "zrb.util.dir_search.Path.resolve",
        side_effect=OSError("bad symlink"),
    ):
        result = get_upward_dirs("/some/path")
    assert result == []


def test_scan_plugin_dirs_collects_valid_manifests(tmp_path):
    plugin_a = tmp_path / "plugin_a" / ".claude-plugin"
    plugin_a.mkdir(parents=True)
    (plugin_a / "plugin.json").write_text("{}")

    plugin_b = tmp_path / "plugin_b"
    plugin_b.mkdir()  # no manifest

    hidden = tmp_path / ".hidden"
    hidden.mkdir()  # excluded by leading dot

    result = scan_plugin_dirs(tmp_path)
    assert tmp_path / "plugin_a" in result
    assert tmp_path / "plugin_b" not in result
    assert hidden not in result


def test_scan_plugin_dirs_returns_empty_on_error():
    bogus = Path("/no/such/dir/anywhere/123")
    # iterdir() on a nonexistent dir raises FileNotFoundError; helper must swallow.
    assert scan_plugin_dirs(bogus) == []


def test_get_dirs_up_to_home_walks_nearest_first(tmp_path):
    home = str(tmp_path)
    nested = str(tmp_path / "a" / "b")
    assert get_dirs_up_to_home(nested, home) == [
        nested,
        str(tmp_path / "a"),
        home,
    ]


def test_get_dirs_up_to_home_outside_home_is_start_only(tmp_path):
    outside = str(tmp_path / "elsewhere")
    assert get_dirs_up_to_home(outside, str(tmp_path / "home")) == [outside]


def test_get_dirs_up_to_home_other_drive_is_start_only():
    with patch("os.path.commonpath", side_effect=ValueError("different drives")):
        assert get_dirs_up_to_home("/x/y", "/x") == ["/x/y"]
