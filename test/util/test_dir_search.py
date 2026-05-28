"""Tests for util/dir_search.py — covers happy paths and exception fallbacks."""

from pathlib import Path
from unittest.mock import patch

from zrb.util.dir_search import get_upward_dirs, scan_plugin_dirs


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
